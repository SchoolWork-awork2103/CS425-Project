# The CS425 diss generator, explained

What the project is, how it works, what our part (System E) is, what we found and what it means. The technical
plans are in `pipeline.md` (whole project), `pipeline_gpt2.md` (System E) and `ARCHITECTURE.md` (code map); this file
explains them in plain terms. Status as of 2026-11-02.

---

## 1. The project in one paragraph

We are building a **chatbot that roasts people in rhyme**. You tell it something you're proud of ("I'm really smart
and ambitious"), and it replies with a four-line poem that turns your brag into a joke against you. Every poem has
the same shape, an **AABB quatrain**: lines 1 and 2 rhyme with each other, and lines 3 and 4 rhyme with each other on
a different sound.

```
[heart]   you say you fill life with romance and keep love near the heart,       A
[apart]   but your cliches are so thick, they drive true feelings far apart.     A
[insight] you claim your wisdom adds depth and gives us fresh insight,           B
[blight]  when it's just a stream of platitudes that chokes the conversation's blight.   B
```
*(A real training diss for the traits "romantic, wise". The words in brackets are each line's planned rhyme word,
more on that in section 4.)*

> **Analogy:** a stand-up comic who takes your humble-brag and flips it, but who is only allowed to answer in one
> strict poem format.

**Two rules shape everything:**
- **No API calls at run time.** Every model runs on our own machines. A big LLM (Qwen3-32B) was used only
  *beforehand*, to write training data. It is not part of the chatbot.
- **One form only (AABB quatrains).** One well-defined form means we can *measure* rhyme precisely and spend the
  effort on quality instead of variety.

---

## 2. How the chatbot answers a message

```
user message → NLU → dialogue manager → rhyme planner → generator (≈20 candidates) → reranker → reply
```

> **Analogy, a restaurant kitchen:**
> - the **waiter (NLU)** works out what you ordered: "a roast, about being smart";
> - the **head chef (dialogue manager)** decides what to do: cook something, ask a question, or make it spicier;
> - the **menu planner (rhyme planner)** picks the rhyme words for the dish;
> - the **cooks (generators)** each make about 20 versions;
> - the **food critic (reranker)** tastes them all and sends out the best one.

| Step | What it does | Status |
|---|---|---|
| **NLU** | Finds the intent (new roast, another one, meaner, softer, hello, bye, off-topic) and the trait words in the message, then maps them to our 40 traits | Done (intent accuracy 94%) |
| **Dialogue manager** | Keeps track of the conversation (traits, mild or harsh, past poems) and decides the next action | In progress (teammate's branch) |
| **Rhyme planner** | Picks two rhyming pairs related to the trait, such as smart → *bright / light, drive / survive* | Done |
| **Generator** | Writes candidate poems that should end on the planned words. Several systems are compared: A, D, E | A and D done; **E done (ours)** |
| **Reranker** | Drops bad candidates (not 4 lines, toxic, gibberish), then scores the rest on rhyme, line length, fluency and trait fit, and picks the best | Trait-fit classifier done; combined score in progress (teammate's branch) |
| **App** | Gradio chat window with a dropdown to pick the generator | In progress (teammate's branch) |

**Why generate 20 and pick 1?** Generators are random and sometimes miss a rhyme. Sampling many and filtering is
cheaper than making one perfect generator, and the reranker is one of the project's own contributions.

---

## 3. The data

| Dataset | Size (train / val / test) | Made by | Used for |
|---|---|---|---|
| **Quatrains:** modern AABB poems on everyday topics | 18,850 / 1,000 | Qwen3-32B, filtered by rhyme rules and a quality judge | "Stage 1" practice: learning to rhyme in four lines |
| **Disses:** AABB roasts for given traits, mild or harsh | 3,382 / 423 / 569 | Qwen3-32B, in the team's roast style, filtered for rhyme, quality and toxicity | "Stage 2": learning to roast |
| NLU messages | 2,624 / 328 / 529 | Qwen3-32B | Training the NLU |
| Reranker negatives | 2,235 | Qwen3-32B and reused data | Teaching the trait-fit classifier what a bad diss looks like |

**Why LLM-generated data?** Old poetry collections (such as Project Gutenberg) are mostly 19th-century verse, which
reads nothing like a modern roast, and few of their four-line chunks rhyme AABB. Generating modern data gave us
exactly the form and style we need.

> **Analogy:** instead of learning to roast from Shakespeare, the students get a custom textbook written by a tutor
> (the big LLM) in today's language.

**Held-out traits.** 5 of the 40 traits (*eloquent, punctual, patient, worldly, frugal*) never appear in any training
data. They are only in the test set.

> **Analogy:** exam questions on a topic that was never in the textbook. A student who only memorised the textbook
> fails them; a student with general knowledge can still answer. That is exactly what they test.

---

## 4. Key ideas, explained simply

**Language model.** A model that predicts the next piece of text, one piece at a time. Writing a poem is just
predicting the next piece over and over.
> **Analogy:** a very advanced phone autocomplete.

**Token.** The pieces a model reads and writes: whole words, parts of words or punctuation. Each model family splits
text its own way (its *tokenizer*), which matters for comparing losses, below.

**Pretraining vs fine-tuning.** *Pretraining*: a model reads a huge amount of general text and learns English.
*Fine-tuning*: we then train it further on our small, specific data.
> **Analogy:** general schooling, then a short job-training course. The more schooling, the less the course has to
> teach.

**Stage 1 and Stage 2.** Every generator except D is trained twice: first on the 18,850 quatrains (rhyming practice,
no roasting), then on the 3,382 disses (the real task).
> **Analogy:** a musician practises scales before learning the song.

**The rhyme plan and end-word tags.** The model is told the four rhyme words up front ("Rhymes: heart apart insight
blight"), and each line it writes starts with its rhyme word in brackets (`[heart] ...`), so it commits to the
ending before writing the line. The tags are removed before the user sees the poem.
> **Analogy:** writing the punchline first, then the setup that leads to it.

**Loss and perplexity.** During training, the model is graded on how much probability it gave to the actual next
token in real poems. *Loss* is that grade as a number where **lower is better**. *Perplexity* is e^loss: perplexity 6
means the model is, on average, as unsure as if it were picking between 6 equally likely tokens.
> **Analogy:** how surprised the model is by real poems. A good model is rarely surprised.

**Losses only compare between models with the same tokenizer.** A, D and E each cut text into different pieces, so
their losses are graded on different "units". E-poems, E-crpo and E-base all use GPT-2's tokenizer, so *their*
losses compare directly.

**Train / validation / test.** The model learns from *train*; we watch *validation* to decide when to stop; *test* is
kept untouched for the final grade.
> **Analogy:** homework, practice tests and the final exam.

**Early stopping and epochs.** An *epoch* is one pass through the training data. After each epoch we check the
validation loss and keep the best epoch; if it stops improving for 2 epochs, training stops. That prevents
*overfitting*, where a model memorises the training data instead of learning from it.
> **Analogy:** studying until your practice-test scores stop going up, rather than until you've memorised the
> answer key.

**Sampling settings.** To get varied poems, the model picks the next token at random, weighted by its probabilities.
*Temperature 0.8* makes it slightly more conservative; *top-p 0.9* ignores the unlikely long tail of tokens; the
*repetition penalty 1.2* discourages reusing words already in the poem. All systems use the same settings, so the
comparison is fair.

**Log-probability.** How likely the model thinks a finished poem is, averaged per token. The reranker uses it as one
signal of fluency: a poem the model finds very unlikely is often clumsy.

---

## 5. The generators we compare

| System | Model | Size | Starts from | How it rhymes |
|---|---|---|---|---|
| **A** | GRU (a small, older kind of network) | 9.3M | Nothing: learns English only from our data | Writes each line **backwards**, starting from the rhyme word, which is forced, so it always ends on the plan |
| **D** | Qwen2.5-1.5B-Instruct + LoRA | 1.5B | A modern model trained on trillions of tokens, then taught to follow instructions | Writes forwards with end-word tags; nothing forces the rhyme |
| **E (ours)** | GPT-2 small, full fine-tune | 124M | GPT-2 (2019), trained on about 40 GB of web text; no instruction training | Like D: forwards with end-word tags |

> **Analogy:**
> - **A** is a student who learned English *only* from our textbook. It can follow the rhyme rules perfectly
>   (because we force the rhyme word in), but it often doesn't make sense.
> - **D** is a well-read adult given a short course. It understands what "frugal" means even though the course never
>   mentioned it.
> - **E** is in between: a high-school student. It knows everyday English, but much less about the world than D.

(Systems B and C in `pipeline.md` are optional and have not been built.)

---

## 6. Our part: System E

### Where it came from
System E began as the `Poem_Model_test` branch: a GPT-2 baseline that started from GPT-2 models **already fine-tuned
on poetry**, found on Hugging Face. The idea was that a model which has already read lots of poems should be better
at writing them.

### Why it is worth having
1. **A size point between A and D.** With A (9M), E (124M) and D (1.5B) we can show how rhyme, sense and trait
   knowledge change with model size and pretraining.
2. **A controlled experiment on poetry pretraining.** Three GPT-2 small checkpoints with the same architecture and
   tokenizer, differing only in what they read beforehand:

   | Name | Checkpoint | Read beforehand |
   |---|---|---|
   | E-poems | `ismaelfaro/gpt2-poems.en` | a Kaggle collection of poems (mostly modern) |
   | E-crpo | `andreipb/gpt2-poetry-model-crpo` | the Gutenberg Poetry Corpus (old verse) |
   | E-base | `gpt2` | no poetry: the control |

   > **Analogy:** three identical students; one did a poetry course, one read Victorian poetry, one did neither.
   > Then all three take the same roast-writing class. Any difference comes from the extra reading.
3. **Cheap and fast.** A full run (both stages) fits on a single small GPU in a couple of hours at most (Stage 2 alone
   took about 12 minutes), and E should answer much faster than D on a CPU (to be measured).

### What we did
| Step | What and why |
|---|---|
| Moved the code into the shared layout | `generation/gpt2_lm.py`, tests, a `gpt2:` section in `config.yaml`; deleted the old baseline folder |
| Made E use the shared data and format | Same quatrains and disses, same information in the prompt as A and D (traits, intensity, rhyme words), end-word tags as in D |
| Fixed the repetition penalty | Hugging Face's built-in penalty also counted the prompt, which lists the rhyme words, so it *pushed the model away from the rhymes it was meant to use*. We used D's penalty, which ignores the prompt and the rhyme words |
| Smoke test, then the training notebook | A tiny run to check everything works end to end, then `generation/train_gpt2.ipynb`, built like A's and D's notebooks |
| Four training runs | E-poems, E-crpo, E-base (all Stage 1 + 2), and E-base with Stage 2 only (to test whether Stage 1 matters) |
| Scored them like A and D | The same 40 + 40 prompts, 4 poems each, with D's scoring code |
| Decoding fixes | Stop as soon as the 4th line is finished; return each poem's log-probability for the reranker |
| Found and fixed a bug (also in D) | The repetition penalty edited the model's scores in place, and those same scores were used for the log-probability, so every poem looked 3 to 10 nats more likely than it really was. Fixed for E; D still has it |

---

## 7. Results

### How the poems were scored
Each system wrote 4 poems for each of 80 prompts: **40 "seen"** (traits from training) and **40 "held-out"** (the 5
unseen traits). Each prompt gives the real diss's rhyme words as the plan.

| Score | Meaning |
|---|---|
| Exactly 4 lines | the poem has the right shape |
| End-word hit | share of lines that end on their planned rhyme word |
| Couplets rhyme | share of couplets (lines 1–2, lines 3–4) that rhyme, by the CMU pronouncing dictionary |
| **Full AABB** | **both couplets rhyme**: the headline form score |
| Syllables | line lengths within the diss limits (6–18 syllables, couplets within 5 of each other) |
| Lexical | share of words that are real words |
| **Trait mention** | **share of poems that name one of their traits or a synonym**: a rough check that the roast is on topic |
| Distinct-2 | variety: share of unique word pairs across all poems (higher = less repetitive) |

### Training (E runs)

| Run | Best Stage 1 val loss | Best Stage 2 val loss | Test loss, seen / held-out |
|---|---|---|---|
| E-poems | 2.097 | 1.925 | 1.93 / 2.09 |
| E-crpo | 2.021 | 1.820 | 1.82 / 2.00 |
| **E-base** | **2.009** | **1.786** | **1.79 / 1.97** |
| E-base, Stage 2 only | (skipped) | 1.933 | 1.94 / 2.16 |

In every full run, Stage 1 was best at epoch 4 of 5, and Stage 2 was still improving very slightly (under 0.01) when
it hit the 5-epoch limit.

### Poems

| | A | D | E-poems | E-crpo | **E-base** | E-base, no Stage 1 |
|---|---|---|---|---|---|---|
| Full AABB, seen | 100% | 81% | 64% | 71% | **74%** | 13% |
| Full AABB, held-out | 100% | 79% | 79% | 84% | **83%** | 11% |
| End-word hit, seen | 100% | 94% | 89% | 91% | 91% | 50% |
| Trait mention, seen | 64% | 78% | 90% | 88% | 88% | 78% |
| **Trait mention, held-out** | **0%** | **69%** | 21% | 39% | **39%** | 23% |
| Distinct-2, seen | 0.55 | 0.66 | 0.64 | 0.61 | 0.63 | 0.71 |
| Exactly 4 lines | 100% | 100% | 99–100% | 100% | 100% | 95–96% |

**A note on noise:** each figure comes from 40 prompts. Differences of a few points (such as E-base 74% vs E-crpo
71%) could flip with different prompts or a different random seed. Only trust gaps of roughly 10 points or more.

What E-base's poems look like (seen traits "smart, ambitious", rhyme plan *bright light drive survive*):
```
you call yourself smart, always talking with a bright,
but your opinions float through the crowd like smoke that's too light.
you're ambitious, ready to push even those drive,
yet all you ever do is cringe and quietly survive.
```
The form is right and it's on topic, but some lines bend the grammar to reach the rhyme word ("talking with a
bright", "push even those drive").

---

## 8. What the results mean for us

### Finding 1: poetry pretraining did not help
E-base, which never read any poetry, has the **lowest loss at every point** and **ties E-crpo** on the poems. E-poems
is worst on both.

Likely reason: our disses are modern, conversational English, which is closer to GPT-2's web text than to old or
amateur poetry. Fine-tuning on poetry may even have worn away some of GPT-2's everyday English. Our own Stage 1
quatrains already teach the rhyming form, so the poetry checkpoints have nothing left to add.

> **Analogy:** training for a modern rap battle by reading Victorian poetry. You learn rhyme, but in the wrong voice,
> and the rap-battle coaching (Stage 1 and 2) teaches the rhyme part anyway.

**For us:** E-base is carried forward as System E. The result goes in the report as a *negative finding*: the original
idea of the branch didn't hold up, which is still a valid and reportable result. It also agrees with the project's
earlier decision to drop Gutenberg data. E-crpo's language turned out *not* to be old-fashioned after fine-tuning.

### Finding 2: Stage 1 (quatrain practice) is essential for E
Without Stage 1, full AABB falls from about 80% to about 12%, and only half the lines end on the planned word.
3,382 disses alone are not enough to learn to follow a rhyme plan; the 18,850 quatrains are.

D managed 81% *without* any Stage 1. D was instruction-trained, so it already knows how to follow directions like
"end this line on *heart*". GPT-2 has no such training and must learn the format from scratch.

> **Analogy:** an experienced professional can follow a new checklist straight away; a beginner needs drills first.

*Caveat:* the Stage 2-only run kept Stage 2's small learning rate, which may slightly under-train a model starting
from plain GPT-2. The gap is so large (74% vs 13%) that it is very unlikely to change the conclusion.

**For us:** this is one of the "with and without Stage 1" ablations the report needs, and a clear one.

### Finding 3: form can be taught; knowledge comes from size
Held-out trait mentions climb with model size and pretraining: **A 0% → E 39% → D 69%**. The rhyme form, though, is
similar for E and D (both about 80% full AABB).

- **Form** (four lines, rhyme on the plan) is learnable by any model, given enough practice (E's Stage 1) or a forcing
  trick (A's backwards lines).
- **Knowing what an unseen word like "frugal" means** cannot come from our small datasets. It has to come from what
  the model read in pretraining, and more pretraining means more knowledge.

**For us:** this is the main story of the A / E / D comparison in the report. It also explains why D is the main
generator: it is the only one that copes with traits it never saw.

### Finding 4: E rhymes about as well as D, at 12× smaller
E-base: 74% / 83% full AABB, D: 81% / 79%. E is a bit behind on seen prompts and level on held-out ones. Neither forces
the rhyme, so for both the reranker has to pick the candidates that do rhyme.

**For us:** E could be a faster demo generator, if its CPU speed is much better than D's (Phase 8 measures this).

### What the results do *not* tell us
- **Whether the poems are funny or make sense.** The scores check form and topic, not humour. Human ratings (Phase
  9) answer that.
- **How E does with the rhyme planner's words.** These tests used the real disses' rhyme words. The planner's words
  are harder: in a quick check, D fell to 54% full AABB with them. E will likely drop too, and the frozen-prompt run
  will show by how much.
- **Anything from losses across systems.** E's losses compare only with other E runs.

---

## 9. Bugs and pitfalls we hit, and why they matter

| Problem | What would have gone wrong | Fix |
|---|---|---|
| Hugging Face's repetition penalty covered the prompt | The prompt lists the rhyme words, so the model was pushed *away* from the rhymes it should use | D's penalty, which skips the prompt and rhyme words |
| The penalty changed the model's scores in place | Every poem's log-probability looked 3–10 nats too high, so the reranker would have trusted it wrongly | Return a new tensor instead of editing in place (E fixed; **D still affected**: its owner should apply the same one-line fix, and any D log-probabilities used for tuning should be regenerated) |
| Training checkpoints saved the optimizer too | 2.8 GB per run of files nothing used | Save only the model weights; delete the temporary run folder |
| Training loss logged every 50 steps | Short runs had no training loss at all | Log once per epoch |
| No stop after the 4th line | A model that started a 5th line ran on to 128 tokens | Stop at the line break after line 4 |

---

## 10. What's next

| # | Task | Depends on |
|---|---|---|
| 1 | **Frozen prompts:** run E-base on the 50 fixed evaluation prompts through the rhyme planner, like every other system | Nothing (needs `python data/prepare_glove.py` once, for the planner) |
| 2 | **Tell D's owner about the penalty bug** | Nothing |
| 3 | **Merge `feat/phase0`** once the teammate's reranker, dialogue manager and app are merged into it | Teammate's branch |
| 4 | **Reranker:** run E's candidates through the filters and combined score; check whether E's log-probability needs its own scaling | Step 3 |
| 5 | **App:** add E to the generator dropdown; measure response time on CPU against A and D | Step 3 |
| 6 | **Ablations for the main table:** E with and without the rhyme planner and the reranker | Steps 1 and 4 |
| 7 | **Report:** E as the mid-size pretrained model, the negative poetry-pretraining result, the Stage 1 result, and checkpoint sources and licences | All of the above |

Optional, if time allows: a Stage 2-only run at a higher learning rate (to settle the caveat in Finding 2), and E
with backwards lines like System A (would force every rhyme, but probably hurt fluency).

---

## 11. Where things are

| What | Where |
|---|---|
| Whole-project plan | `pipeline.md` |
| System E plan and change log | `pipeline_gpt2.md` |
| Code map and status | `ARCHITECTURE.md` |
| E's code and tests | `generation/gpt2_lm.py`, `generation/test_gpt2_lm.py` |
| E's training notebook | `generation/train_gpt2.ipynb` |
| E's results | `eval/results/gen_E/` (README and one summary JSON per run) |
| A's and D's results | `eval/results/gen_A/`, `eval/results/gen_D/` |
| E's trained models | `checkpoints/gen_E_*_best/` locally and on the shared Drive (`MyDrive/CS425/checkpoints/`) |
