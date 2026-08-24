import { neon } from '@neondatabase/serverless';
import dotenv from 'dotenv';

dotenv.config();

if (!process.env.DATABASE_URL) {
    console.error("DATABASE_URL is not set.");
    process.exit(1);
}

const sql = neon(process.env.DATABASE_URL);

async function migrateCalendar() {
    try {
        await sql`
            CREATE TABLE IF NOT EXISTS calendar_entries (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                link TEXT,
                snippet TEXT,
                is_literature BOOLEAN DEFAULT TRUE,
                categories TEXT[],
                ai_rating INTEGER,
                ai_reason TEXT,
                ai_checked BOOLEAN DEFAULT FALSE,
                date_min_str VARCHAR(5),
                date_max_str VARCHAR(5),
                date_focus_str VARCHAR(5),
                date_min_d SMALLINT,
                date_max_d SMALLINT,
                date_focus_d SMALLINT,
                day_of_week VARCHAR(15),
                day_of_week_num SMALLINT
            )
        `;

        await sql`
            ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_min_str VARCHAR(5);
            ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_max_str VARCHAR(5);
            ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_focus_str VARCHAR(5);
            ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_min_d SMALLINT;
            ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_max_d SMALLINT;
            ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS date_focus_d SMALLINT;
            ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS day_of_week VARCHAR(15);
            ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS day_of_week_num SMALLINT;
            ALTER TABLE calendar_entries DROP COLUMN IF EXISTS valid_dates;
        `;

        await sql`
            CREATE TABLE IF NOT EXISTS calendar_votes (
                id SERIAL PRIMARY KEY,
                entry_id INTEGER REFERENCES calendar_entries(id),
                rating INTEGER CHECK (rating >= 0 AND rating <= 5),
                date_class VARCHAR(20),
                corrected_date TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        `;

        await sql`CREATE INDEX IF NOT EXISTS idx_calendar_entries_ai_checked ON calendar_entries(ai_checked)`;
        await sql`CREATE INDEX IF NOT EXISTS idx_calendar_votes_entry_id ON calendar_votes(entry_id)`;
        await sql`CREATE INDEX IF NOT EXISTS idx_cal_date_min_d ON calendar_entries(date_min_d)`;
        await sql`CREATE INDEX IF NOT EXISTS idx_cal_date_max_d ON calendar_entries(date_max_d)`;
        await sql`CREATE INDEX IF NOT EXISTS idx_cal_dow ON calendar_entries(day_of_week_num)`;

        console.log("Calendar migration successful.");
    } catch (e) {
        console.error("Calendar migration failed:", e);
    }
}

migrateCalendar();
