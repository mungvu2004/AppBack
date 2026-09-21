import { z } from 'zod';

import { isoInstantSchema } from '@/api/schemas/common';
import { AUTH_ROLES } from '@/lib/auth/permissions';

/**
 * Thân 200 của `POST /api/auth/refresh`, ghim chặt đúng W16 (BE-00 §3, K04).
 *
 * Schema của FE (`src/lib/auth/refresh.ts:196-220`) là `.passthrough()` và lùi
 * `roles` về `[]` khi vắng, nên nó không bắt được vai thứ tư, vai viết hoa hay
 * thiếu hẳn `roles`. Golden `auth_refresh` vì thế giải bằng bản này: `.strict()`
 * ở mọi tầng, `roles` là tuple **đúng một** vai của `AUTH_ROLES`, `expiresAt`
 * là ISO UTC `Z` đúng 3 chữ số (`isoInstantSchema` của FE, W3), `user.id` là
 * `usr_` + ULID (W4). Vai và mẫu ngày giờ nhập từ FE ở SHA ghim để không trôi.
 *
 * Cấm nới bằng `.passthrough()` (B0-07 [9]).
 */
export const RefreshResponseSchema = z
  .object({
    accessToken: z.string().min(1),
    expiresAt: isoInstantSchema,
    roles: z.tuple([z.enum(AUTH_ROLES)]),
    user: z
      .object({
        email: z.string().email(),
        id: z.string().regex(/^usr_[0-9A-HJKMNP-TV-Z]{26}$/),
        name: z.string().min(1),
      })
      .strict(),
  })
  .strict();
