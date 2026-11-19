# Quatrain corpus: generation record (Phase 1a.9)

Source notebook: `data/quatrains/quatrain_gen.ipynb` (MODE = "full", MODEL = "qwen3-32b"). Run finished 2026-10-22.
Raw statistics: `meta.json`; per-chunk rejection reasons: `progress.jsonl`. Cleaning and split: `data/quatrains/corpus/prep_meta.json`.

## Model and sampling
| Setting | Value |
|---|---|
| Model | Qwen/Qwen3-32B-FP8, thinking off, vLLM on an L40 |
| Candidates per prompt | 4 |
| Temperature / top-p / repetition penalty | 0.9 / 0.95 / 1.05 |
| Max tokens | 200 |
| Seed | 42 (chunk k uses seed 42 × 100003 + k) |
| Prompts | 2,000 per chunk, 36 chunks (the last partial), about 72,000 in total |
| Output tokens / time | the full run's totals are not in `meta.json`, which covers the last resumed session only (28,000 prompts, 8.1M tokens, 3.6 h) |

## Prompt
Each prompt combines one of 797 topics (`data/quatrains/topics.json`), one of 14 tones (funny, sarcastic, wistful, hopeful, deadpan, dramatic, playful, grumpy, tender, nostalgic, anxious, cheerful, bittersweet, proud) and one of 3 voices (first person, second person, narrator). Two of four worked examples are given as earlier chat turns.

System message:
> You write short modern poems in rhyming couplets. Reply with a RHYMES line, then exactly 4 lines of poetry, each starting with its end word in square brackets. No title, no blank lines, no explanation.

User message:
> Write one quatrain made of two rhyming couplets (AABB).
> - Line 1 rhymes with line 2. Line 3 rhymes with line 4.
> - The second couplet uses a different rhyme sound. Line 1 must not rhyme with line 3.
> - 7 to 11 syllables per line.
> - Every line must make sense on its own. Never add words just to reach a rhyme.
> - Modern everyday English. No archaic words, no cliches, simple punctuation.
> - Avoid overused rhymes like night/light, heart/apart, day/way.
>
> Topic: {topic} / Tone: {tone} / Voice: {voice}
> First write the RHYMES line with the end words of each couplet. Then write the 4 lines; start each one with its end word in square brackets, and end the line with exactly that word.

## Form checks (per candidate)
- exactly 4 lines; lines 1–2 and 3–4 rhyme (CMUdict rhyming part); A and B sounds differ; no identical rhymes (play/replay, one/won)
- 6–12 syllables per line, couplet lines within 3 syllables of each other
- at most 15% of words missing from CMUdict; end words wordfreq Zipf ≥ 2.5

## Quality judge
Same model, temperature 0, candidates passing the form checks; kept if score ≥ 4. Rubric:
> Rate this short modern poem from 1 to 5 for sense and naturalness. Ignore rhyme and metre, which are checked separately.
> 5 = every line makes sense, sounds like something a person would really say, and fits the topic
> 4 = good overall, at most one slightly awkward phrase
> 3 = understandable, but at least one phrase is there only for the rhyme or does not quite make sense
> 2 = several forced or nonsensical phrases
> 1 = mostly nonsense or off topic

Four calibration examples (scored 2, 3, 4, 5) are included in the prompt; see cell 14 of the notebook.

## Dataset filters
Exact duplicates; near-duplicates (ROUGE-L F1 > 0.7 against saved quatrains sharing a rhyme pair); quatrains reusing 2+ earlier lines; rhyme pairs already used 50 times; copies of the worked examples. Per prompt, the highest-scoring passing candidate is saved (ties: least-used rhyme pairs).

## Results
- 20,000 quatrains saved; judge scores 4: 14,247, 5: 5,753
- 5,570 distinct rhyme pairs, 2,720 distinct end words, 241 pairs at the cap of 50
- Kept per 2,000-prompt chunk fell from 1,178 (chunk 0) to about 320 (chunks 29–34) as the rhyme-pair cap rejected more candidates (31 → about 1,300 per chunk). Scaling to 50k would need more topics, not only more chunks.
- Last session (28,000 prompts): 35% of candidates passed the form checks, 60% of those passed the judge (mean 3.74), and 81% of lines ended with their tagged end word.

## Known issue found after the run
The parser only stripped a `[word]` tag at the **start** of a line. In 58 quatrains the model put it at the end, so the tag was read as the end word and the rhyme check passed on the wrong word. These are removed in `data/quatrains/prepare_quatrains.py`, together with 5 quatrains containing Chinese characters and 87 containing digits or symbols. The 1b diss notebook must reject any line containing brackets.
