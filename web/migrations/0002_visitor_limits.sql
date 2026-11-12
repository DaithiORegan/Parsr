-- No CV text, review output, or raw IP addresses are stored here.
CREATE TABLE IF NOT EXISTS visitor_limits (bucket TEXT PRIMARY KEY, used INTEGER NOT NULL, expires INTEGER NOT NULL);
