// Board matching from the board profile (boards/<slug>.json) — same rule as
// chat_ops.py BASE_URL / boards.py. Default board: lucky-break-payday.
import fs from 'node:fs';

export const BOARD = (() => {
  const slug = process.env.HERMES_BOARD || 'lucky-break-payday';
  try {
    return JSON.parse(fs.readFileSync(new URL(`../../boards/${slug}.json`, import.meta.url), 'utf8'));
  } catch {
    return {name: slug, url: `https://app.grayswan.ai/arena/challenge/${slug}`, match: slug};
  }
})();

export const BOARD_MATCH = String(BOARD.match || BOARD.name || 'lucky-break-payday');