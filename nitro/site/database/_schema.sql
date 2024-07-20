CREATE TABLE IF NOT EXISTS "ticket_msgs" (
        "content"       TEXT,           -- "cheers mate"
        "author"        INTEGER,        -- 1
        "ticket"        INTEGER,        -- 1
        "seen_by"       TEXT,           -- "-1--2--5-"
        "time"          INTEGER         -- 1680875819
);

CREATE TABLE IF NOT EXISTS "credits" (
        "change"        TEXT,           -- "3"
        "user"          INTEGER,        -- 1
        "reason"        TEXT,           -- "Sellix: ***" (redacted)
        "balance"       INTEGER,        -- 3
        "time"          INTEGER         -- 1680875819
);

CREATE TABLE IF NOT EXISTS "tickets" (
        "author"        INTEGER,        -- 5
        "creation_time" INTEGER,        -- 1680875819
        "open"          INTEGER,        -- 0
        "first_reply"   INTEGER         -- 1680946548
);

CREATE TABLE IF NOT EXISTS "cookies" (
        "cookie"    TEXT,               -- "YB5oyQcSLypUc9iPYDEKb***" (redacted)
        "user"      INTEGER,            -- 1
        "time"      INTEGER,            -- 1680875819
        "agent"     TEXT,               -- "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
        "ip"        TEXT                -- "12.**" (redacted)
);

CREATE TABLE IF NOT EXISTS "users" (
        "username"          TEXT,       -- "luxury"
        "display_name"      TEXT,       -- "Luxury"
        "email"             TEXT,       -- "d**@gmail.com" (redacted)
        "password"          TEXT,       -- "$2b$12$****"  (redacted, bcrypt hash)
        "email_verified"    TEXT,       -- "True"
        "role"              TEXT,       -- "Admin" (can be "User")
        "ips"               TEXT,       -- "["26***", "2601:4***"]" (redacted)
        "time"              INTEGER     -- 1680874808
);

CREATE TABLE IF NOT EXISTS "recover" (
        "key"   TEXT,           -- "tOUM4EE2JKiKoYTl4tUq***" (redacted)
        "user"  INTEGER,        -- 12
        "time"  INTEGER         -- 1680874808
);

CREATE TABLE IF NOT EXISTS "orders" (
        "user"          INTEGER,        -- 1
        "quantity"      INTEGER,        -- 1
        "timestamp"     INTEGER,        -- 1680874808
        "status"        INTEGER,        -- 2 (0=queued, 1=claiming, 2=done)
        "claim_data"    TEXT,           -- "[{"instance": "4", "time": 1680887047, "type": "Basic Monthly"}]"
        "referral"      TEXT,           -- "1" (this is the actual order id, read README.md for more info)
        "token"         TEXT,           -- "order_completed" (would be discord token, b64(userid), or "order_completed")
        "anonymous"     INTEGER         -- 0
);

CREATE TABLE IF NOT EXISTS "paypal" ( -- legacy, not used
        "id"    TEXT,   -- "1LD70730**" (redacted)
        "data"  TEXT    -- "claimed"
);

CREATE TABLE IF NOT EXISTS "webhooks" (
        "user"          INTEGER,        -- 1
        "url"           TEXT,           -- "https://discord.com/api/webhooks/11295102***"
        "emojis"        TEXT,           -- "{"basic": "<:nitro_basic:1093984571839758417>", "boost": "<:nitro_boost:1093986192346849310>", "classic": "<:nitro_classic:1129332873728634970>"}"
        "message"       TEXT            -- "[emoji] Claimed `[nitro]` for [user] `(#[order]) ([claimed]/[quantity])` in `[time]`."
);
