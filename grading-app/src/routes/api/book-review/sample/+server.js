import { sql } from '$lib/server/db';
import { json } from '@sveltejs/kit';

export async function GET({ url }) {
    try {
        const dataset = url.searchParams.get('dataset') === 'date' ? 'date' : 'time';
        const title = url.searchParams.get('title');
        const limitParam = Number.parseInt(url.searchParams.get('limit') ?? '50', 10);
        const limit = Number.isFinite(limitParam) ? Math.min(Math.max(limitParam, 1), 200) : 50;

        if (!title) {
            return json({ error: 'Missing title' }, { status: 400 });
        }

        const rows = dataset === 'date'
            ? await sql`
                SELECT id, title, NULL::text AS author, snippet, valid_dates, ai_checked, ai_rating, ai_reason, link
                FROM calendar_entries
                WHERE title = ${title}
                ORDER BY RANDOM()
                LIMIT ${limit}
            `
            : await sql`
                SELECT id, title, NULL::text AS author, snippet,
                       time_min_str, time_max_str, time_focus_str,
                       CASE
                           WHEN time_min_str IS NULL THEN ''
                           WHEN time_max_str IS NULL OR time_min_str = time_max_str THEN time_min_str
                           ELSE time_min_str || ' – ' || time_max_str
                       END AS display_time,
                       ai_checked, ai_rating, ai_reason, link
                FROM entries
                WHERE title = ${title}
                ORDER BY RANDOM()
                LIMIT ${limit}
            `;

        return json({ dataset, title, sample: rows });
    } catch (e) {
        console.error('Book review sample error:', e);
        return json({ error: 'Failed to load sample' }, { status: 500 });
    }
}
