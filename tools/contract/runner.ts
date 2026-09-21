/**
 * Runner hợp đồng FE của bước 7 (B0-07, BE-00 §12): giải mẫu golden bằng
 * **chính** schema zod của AppFront ở SHA ghim, không chép lại schema nào.
 *
 * `node --import tsx runner.ts <lệnh> <file JSON vào>`; in đúng một JSON ra
 * stdout và thoát 0 khi chạy xong — kết quả hỏng nằm **trong** JSON. Thoát khác 0
 * chỉ khi chính runner hỏng (lệnh lạ, file vào hỏng, module FE ném lúc nạp);
 * `check.py` coi đó là bước 7 hỏng và in stderr.
 *
 * Lệnh:
 * - `smoke {schemaModules}` → `{problems, shapes}`: nhập mọi module schema và mọi
 *   mục của `schema-map.ts`, kiểm mỗi `exportName` là schema zod;
 * - `decode {samples}` → `{verdicts}`: giải từng mẫu (H1, H5) rồi chạy H1 ngữ cảnh;
 * - `permissions {}` → `{roles, keys, matrix}` (H3);
 * - `rules {}` → `{codes, thresholds}` (H4).
 */
import { readFileSync } from 'node:fs';

import { z } from 'zod';

import { contextRuleFor } from './context';
import { SCHEMA_MAP, type SchemaMapEntry } from './schema-map';

const SHAPES = new Set(['object', 'array', 'empty']);

interface SampleIn {
  readonly file: string;
  readonly operationId: string;
  readonly status?: number;
  readonly event?: boolean;
  readonly body: unknown;
  readonly pathParams?: Record<string, string>;
  readonly context?: Record<string, unknown>;
}

interface Verdict {
  file: string;
  decode: 'ok' | 'fail';
  reason?: string;
  context: 'ok' | 'fail' | 'none';
  contextReason?: string;
}

/** Câu ngắn của một ngoại lệ bất kỳ (lỗi nhập module, export thiếu). */
function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** Mục của bản đồ, hay `undefined`; `hasOwn` để `constructor` không khớp nhầm. */
function entryOf(operationId: string): SchemaMapEntry | undefined {
  return Object.hasOwn(SCHEMA_MAP, operationId) ? SCHEMA_MAP[operationId] : undefined;
}

/** Schema zod của một mục; `array` bọc thêm `z.array`. Export thiếu hay không phải zod → ném. */
async function schemaOf(entry: SchemaMapEntry): Promise<z.ZodTypeAny> {
  if (entry.shape === 'empty') {
    throw new Error('mục empty không có schema');
  }
  const module = (await import(entry.module)) as Record<string, unknown>;
  const schema = module[entry.exportName];
  if (!(schema instanceof z.ZodType)) {
    throw new Error(`${entry.module} không export schema zod "${entry.exportName}"`);
  }
  return entry.shape === 'array' ? z.array(schema) : schema;
}

/** Lỗi đầu mục (thiếu module/tên, shape lạ) — TS không kiểm lúc chạy vì tsx không typecheck. */
function entryProblem(operationId: string, entry: SchemaMapEntry): string | null {
  if (!SHAPES.has(entry.shape)) {
    return `${operationId}: shape "${String(entry.shape)}" không thuộc object|array|empty`;
  }
  if (entry.shape !== 'empty' && (!entry.module || !entry.exportName)) {
    return `${operationId}: thiếu module hay exportName`;
  }
  return null;
}

/** Smoke: nhập mọi module schema FE rồi mọi mục của bản đồ. */
async function smoke(input: { schemaModules: string[] }): Promise<unknown> {
  const problems: string[] = [];
  for (const module of input.schemaModules) {
    try {
      await import(module);
    } catch (error) {
      problems.push(`nhập ${module} hỏng: ${messageOf(error)}`);
    }
  }
  const shapes: Record<string, string> = {};
  for (const [operationId, entry] of Object.entries(SCHEMA_MAP)) {
    shapes[operationId] = entry.shape;
    const problem = entryProblem(operationId, entry);
    if (problem !== null) {
      problems.push(problem);
    } else if (entry.shape !== 'empty') {
      await schemaOf(entry).catch((error: unknown) => problems.push(`${operationId}: ${messageOf(error)}`));
    }
  }
  return { problems, shapes };
}

/** Thân 409 `VERSION_CONFLICT` chọn schema riêng (W7, W20); mọi lỗi khác là `ApiErrorBodySchema`. */
async function errorSchemaFor(body: unknown): Promise<z.ZodTypeAny> {
  const errors = await import('@/api/schemas/errors');
  const code = body !== null && typeof body === 'object' ? (body as Record<string, unknown>).code : undefined;
  return code === 'VERSION_CONFLICT' ? errors.VersionConflictBodySchema : errors.ApiErrorBodySchema;
}

/**
 * Schema để giải một mẫu, hay câu hỏng khi mẫu hỏng mà không cần giải; `null` = thân
 * rỗng hợp lệ (204, mục `empty`). Luật chọn: B0-07 [2] "Chọn schema cho H1".
 */
async function schemaForSample(sample: SampleIn): Promise<z.ZodTypeAny | string | null> {
  const entry = entryOf(sample.operationId);
  if (entry === undefined) {
    return 'thao tác không có trong schema-map.ts';
  }
  const status = sample.status ?? 200;
  if (!sample.event && status >= 400) {
    return errorSchemaFor(sample.body);
  }
  if (!sample.event && (status < 200 || status >= 300)) {
    return `status ${status} ngoài hợp đồng (chỉ 2xx và ≥ 400)`;
  }
  if (status === 204 || entry.shape === 'empty') {
    return sample.body === null ? null : `status ${status} (shape ${entry.shape}) phải có thân rỗng`;
  }
  return schemaOf(entry);
}

/** Giải một mẫu rồi chạy luật ngữ cảnh của thao tác lên đầu ra (chỉ 2xx và khung luồng). */
async function decodeOne(sample: SampleIn): Promise<Verdict> {
  const verdict: Verdict = { context: 'none', decode: 'ok', file: sample.file };
  const schema = await schemaForSample(sample);
  if (typeof schema === 'string') {
    return { ...verdict, decode: 'fail', reason: schema };
  }
  if (schema === null) {
    return verdict;
  }
  const parsed = schema.safeParse(sample.body);
  if (!parsed.success) {
    const issue = parsed.error.issues[0]!;
    return { ...verdict, decode: 'fail', reason: `safeParse hỏng: path=${JSON.stringify(issue.path)} code=${issue.code}` };
  }
  const rule = contextRuleFor(sample.operationId);
  const isSuccess = sample.event || (sample.status ?? 200) < 300;
  if (rule === undefined || !isSuccess) {
    return verdict;
  }
  const failure = rule(parsed.data as Record<string, unknown>, sample.pathParams ?? {}, sample.context ?? {});
  return failure === null ? { ...verdict, context: 'ok' } : { ...verdict, context: 'fail', contextReason: failure };
}

/** Giải mọi mẫu, giữ thứ tự vào. */
async function decode(input: { samples: SampleIn[] }): Promise<unknown> {
  const verdicts: Verdict[] = [];
  for (const sample of input.samples) {
    verdicts.push(await decodeOne(sample));
  }
  return { verdicts };
}

/** H3: vai và ma trận quyền của FE, giữ thứ tự khoá của `permissionMatrix`. */
async function permissions(): Promise<unknown> {
  const { AUTH_ROLES, permissionMatrix } = await import('@/lib/auth/permissions');
  return { keys: Object.keys(permissionMatrix), matrix: permissionMatrix, roles: [...AUTH_ROLES] };
}

/** H4: mã của `ALL_RULES` (không phải `BUILT_IN_RULES`, chỉ là nhóm con) và khoá ngưỡng. */
async function rules(): Promise<unknown> {
  const { ALL_RULES } = await import('@/domain/rules/defaults');
  const { RULE_THRESHOLD_SPECS } = await import('@/domain/rules/thresholdSpecs');
  return {
    codes: ALL_RULES.map((rule) => rule.code),
    thresholds: RULE_THRESHOLD_SPECS.map((spec) => ({
      key: spec.key,
      max: spec.max,
      min: spec.min,
      ruleCode: spec.ruleCode,
    })),
  };
}

const COMMANDS: Readonly<Record<string, (input: never) => Promise<unknown>>> = { decode, permissions, rules, smoke };

const [command = '', inputPath] = process.argv.slice(2);
if (!Object.hasOwn(COMMANDS, command) || inputPath === undefined) {
  process.stderr.write(`dùng: runner.ts <${Object.keys(COMMANDS).join('|')}> <file JSON vào>\n`);
  process.exit(2);
}
const input = JSON.parse(readFileSync(inputPath, 'utf8')) as never;
process.stdout.write(JSON.stringify(await COMMANDS[command]!(input)));
