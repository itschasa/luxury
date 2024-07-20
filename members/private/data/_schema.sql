CREATE TABLE IF NOT EXISTS "users" (
	"id"			INTEGER,
	"name"			TEXT,
	"email"			TEXT,
	"password"		TEXT,
	"ips"			TEXT,
	"verified"		INTEGER,
	"kickoff_time"	INTEGER,
	"display_name"	TEXT,
	"api_expire"	INTEGER,
	PRIMARY KEY("id")
);

CREATE TABLE IF NOT EXISTS "tokens" (
	"token"				TEXT,
	"user_id"			INTEGER,
	"raw_token"			TEXT,
	"status"			INTEGER,
	"access_token"		TEXT,
	"access_expire"		INTEGER,
	"refresh_token"		TEXT,
	"guild_count"		INTEGER,
	"added_on"			INTEGER,
	"type"				INTEGER,
	"guilds"			TEXT,
	"boosts_remaining"	INTEGER,
	PRIMARY KEY("user_id")
);

CREATE TABLE IF NOT EXISTS "orders" (
	"id"			INTEGER,
	"status"		INTEGER,
	"user_id"		INTEGER,
	"order_data"	TEXT,
	"guild_id"		INTEGER,
	"role_ids"		TEXT,
	PRIMARY KEY("id"),
	FOREIGN KEY("user_id") REFERENCES "users"("id")
);

CREATE TABLE IF NOT EXISTS "payments" (
	"id"		INTEGER,
	"change"	INTEGER,
	"user_id"	INTEGER,
	"reason"	TEXT,
	"order_id"	INTEGER,
	"balance"	INTEGER,
	FOREIGN KEY("user_id") REFERENCES "users"("id"),
	FOREIGN KEY("order_id") REFERENCES "orders"("id"),
	PRIMARY KEY("id")
);
