import { neon } from '@neondatabase/serverless';
import fs from 'fs';
import readline from 'readline';
import dotenv from 'dotenv';

dotenv.config();

const DATABASE_URL = process.env.DATABASE_URL;
const INPUT_FILE = '../scrapers/mek_search/mek_search_results.jsonl';

if (!DATABASE_URL) {
  console.error("DATABASE_URL not found in .env");
  process.exit(1);
}

const sql = neon(DATABASE_URL);

async function seed() {
  console.log("Starting seeding process...");

  // Create tables
  await sql`DROP TABLE IF EXISTS votes CASCADE`;
  await sql`DROP TABLE IF EXISTS entries CASCADE`;
  await sql`
    CREATE TABLE entries (
      id SERIAL PRIMARY KEY,
      title TEXT NOT NULL,
      link TEXT,
      snippet TEXT,
      is_literature BOOLEAN,
      time_min_str VARCHAR(7),
      time_max_str VARCHAR(7),
      time_focus_str VARCHAR(7),
      time_min_m SMALLINT,
      time_max_m SMALLINT,
      time_focus_m SMALLINT,
      categories TEXT[]
    )
  `;
  await sql`
    CREATE TABLE votes (
      id SERIAL PRIMARY KEY,
      entry_id INTEGER REFERENCES entries(id),
      rating INTEGER CHECK (rating >= 1 AND rating <= 5),
      am_pm VARCHAR(20),
      created_at TIMESTAMP DEFAULT NOW()
    )
  `;

  const fileStream = fs.createReadStream(INPUT_FILE);
  const rl = readline.createInterface({
    input: fileStream,
    crlfDelay: Infinity
  });

  let count = 0;
  let batch = [];
  const BATCH_SIZE = 100; // Smaller batches for HTTP driver stability

  for await (const line of rl) {
    if (!line.trim()) continue;
    try {
      const data = JSON.parse(line);
      const timeMinStr = data.time_min_str || data.norm_time || null;
      const timeMaxStr = data.time_max_str || timeMinStr;
      const timeFocusStr = data.time_focus_str || timeMinStr;
      const parseM = (s) => {
        if (!s || !s.includes(':')) return null;
        const [h, m] = s.split(':').map(Number);
        return isNaN(h) || isNaN(m) ? null : h * 60 + m;
      };
      const timeMinM = data.time_min_m !== undefined ? data.time_min_m : parseM(timeMinStr);
      const timeMaxM = data.time_max_m !== undefined ? data.time_max_m : parseM(timeMaxStr);
      const timeFocusM = data.time_focus_m !== undefined ? data.time_focus_m : parseM(timeFocusStr);

      batch.push({
        title: data.title || '',
        link: data.link || '',
        snippet: data.snippet || '',
        is_literature: !!data.is_literature,
        time_min_str: timeMinStr,
        time_max_str: timeMaxStr,
        time_focus_str: timeFocusStr,
        time_min_m: timeMinM,
        time_max_m: timeMaxM,
        time_focus_m: timeFocusM,
        categories: data.topics || []
      });

      if (batch.length >= BATCH_SIZE) {
        await insertBatch(batch);
        count += batch.length;
        process.stdout.write(`\rInserted ${count} entries...`);
        batch = [];
      }
    } catch (e) {
      console.error("\nError parsing line:", e.message);
    }
  }

  if (batch.length > 0) {
    await insertBatch(batch);
    count += batch.length;
    console.log(`\rInserted ${count} entries.`);
  }

  console.log("\nSeeding completed successfully.");
}

async function insertBatch(batch) {
  // Construct a single multi-row insert query
  const values = [];
  const placeholders = [];
  
  batch.forEach((item, i) => {
    const offset = i * 11;
    placeholders.push(`($${offset + 1}, $${offset + 2}, $${offset + 3}, $${offset + 4}, $${offset + 5}, $${offset + 6}, $${offset + 7}, $${offset + 8}, $${offset + 9}, $${offset + 10}, $${offset + 11})`);
    values.push(item.title, item.link, item.snippet, item.is_literature, item.time_min_str, item.time_max_str, item.time_focus_str, item.time_min_m, item.time_max_m, item.time_focus_m, item.categories);
  });

  const query = `
    INSERT INTO entries (title, link, snippet, is_literature, time_min_str, time_max_str, time_focus_str, time_min_m, time_max_m, time_focus_m, categories) 
    VALUES ${placeholders.join(', ')}
  `;

  await sql(query, values);
}

seed().catch(err => {
  console.error("\nSeeding failed:", err);
  process.exit(1);
});
