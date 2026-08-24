import { sql } from '$lib/server/db';
import { json } from '@sveltejs/kit';

export async function GET({ url }) {
    try {
        const dataset = url.searchParams.get('dataset') === 'date' ? 'date' : 'time';

        let entry = null;
        let attempts = 0;
        let isReGrade = false;

        // 10% chance to fetch an entry previously denied by AI
        if (Math.random() < 0.1) {
            const reGradeResult = dataset === 'date'
                ? await sql`
                    SELECT e.* FROM calendar_entries e
                    WHERE e.is_literature = true
                    AND e.ai_checked = true
                    AND EXISTS (
                        SELECT 1 FROM calendar_votes v
                        WHERE v.entry_id = e.id
                        AND v.corrected_date = 'AI_DENY'
                    )
                    AND NOT EXISTS (
                        SELECT 1 FROM calendar_votes v2
                        WHERE v2.entry_id = e.id
                        AND (v2.corrected_date IS NULL OR v2.corrected_date != 'AI_DENY')
                    )
                    ORDER BY RANDOM()
                    LIMIT 1
                `
                : await sql`
                    SELECT e.* FROM entries e
                    WHERE e.is_literature = true
                    AND e.ai_checked = true
                    AND EXISTS (
                        SELECT 1 FROM votes v
                        WHERE v.entry_id = e.id
                        AND v.corrected_time = 'AI_DENY'
                    )
                    AND NOT EXISTS (
                        SELECT 1 FROM votes v2
                        WHERE v2.entry_id = e.id
                        AND (v2.corrected_time IS NULL OR v2.corrected_time != 'AI_DENY')
                    )
                    ORDER BY RANDOM()
                    LIMIT 1
                `;
            if (reGradeResult.length > 0) {
                entry = reGradeResult[0];
                isReGrade = true;
            }
        }
        
        // Check if AI checked entries exist once before loop
        let hasAiChecked = true;
        if (dataset !== 'date') {
            const check = await sql`SELECT 1 FROM entries WHERE ai_checked = true AND is_literature = true LIMIT 1`;
            hasAiChecked = check.length > 0;
        }

        // Find a valid entry, auto-denying bad ones
        while (!entry && attempts < 20) {
            attempts++;
            const result = dataset === 'date'
                ? await sql`
                    SELECT * FROM calendar_entries
                    WHERE id NOT IN (SELECT entry_id FROM calendar_votes)
                    AND is_literature = true
                    ORDER BY RANDOM()
                    LIMIT 1
                `
                : (hasAiChecked
                    ? await sql`
                        SELECT * FROM entries
                        WHERE id NOT IN (SELECT entry_id FROM votes)
                        AND is_literature = true
                        AND ai_checked = true
                        ORDER BY RANDOM()
                        LIMIT 1
                    `
                    : await sql`
                        SELECT * FROM entries
                        WHERE id NOT IN (SELECT entry_id FROM votes)
                        AND is_literature = true
                        ORDER BY RANDOM()
                        LIMIT 1
                    `);
            
            const candidate = result[0];
            if (!candidate) break;

            const snippetText = candidate.snippet ? candidate.snippet.toLowerCase() : "";
            const isInvalid = !candidate.snippet || 
                              candidate.snippet.trim() === "" || 
                              snippetText.includes("no snippet is available");

            if (isInvalid) {
                // Auto-deny
                if (dataset === 'date') {
                    await sql`
                        INSERT INTO calendar_votes (entry_id, rating, date_class)
                        VALUES (${candidate.id}, 0, 'ambiguous')
                    `;
                } else {
                    await sql`
                        INSERT INTO votes (entry_id, rating, am_pm)
                        VALUES (${candidate.id}, 0, 'ambiguous')
                    `;
                }
                continue;
            }
            
            entry = candidate;
        }

        if (!entry) {
            return json({ error: "No valid entries available" }, { status: 404 });
        }

        return json({ ...entry, is_re_grade: isReGrade, dataset });
    } catch (e) {
        console.error("DB Error:", e);
        return json({ error: "Database connection failed" }, { status: 500 });
    }
}
