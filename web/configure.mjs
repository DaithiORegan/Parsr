import { readFile, writeFile } from "node:fs/promises";
const config = JSON.parse(await readFile("wrangler.jsonc", "utf8"));
if (!process.env.D1_DATABASE_ID) throw Error("Missing D1_DATABASE_ID");
if (!/^[a-f0-9-]{36}$/i.test(process.env.D1_DATABASE_ID))
  throw Error("Invalid D1_DATABASE_ID");
config.d1_databases[0].database_id = process.env.D1_DATABASE_ID;
for (const name of ["ACCESS_TEAM_DOMAIN", "ACCESS_AUD", "OWNER_EMAIL"])
  if (process.env[name]) config.vars[name] = process.env[name];
await writeFile("wrangler.jsonc", JSON.stringify(config, null, 2) + "\n");
