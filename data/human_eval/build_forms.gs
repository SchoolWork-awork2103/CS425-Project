// Built by eval/human_eval.py. At script.google.com: New project, paste this over the code, Save.
// Then choose buildRater1 and Run, then buildRater2, and so on: one rater per run, since Apps Script stops a run
// after 6 minutes and all raters in one run could pass that. Each run makes that rater's 3 forms and logs the
// links to send them (Execution log). If a run stops partway, delete the forms it made (Google Drive) and run it
// again. Every form also writes its responses to one spreadsheet, "<title> (responses)", a tab per rater and part:
// download each tab (File > Download > CSV) as data/human_eval/responses/rater_<k>_part<p>.csv.
// Only the buildRater<k> functions show in the Run menu: the helpers end in "_", which keeps them out of it.
function buildRater1() { buildRater_(1); }
function buildRater2() { buildRater_(2); }
function buildRater3() { buildRater_(3); }

const DATA = {
 "title": "Rate the roast poems",
 "intro": "Thank you for helping!\n\nA chatbot writes short roast poems: someone tells it what they are proud of, and it answers with a four-line poem that teases them about it. Several versions of the bot wrote the poems you will see.\n\nThere are 30 requests, each with up to 3 poems, in 3 parts of 10 requests: this form is one part, and you have a separate link for each. Rate every poem from 1 to 5 on five criteria. Each part takes about 15-20 minutes. Submit a part before taking a break: an unsubmitted form is lost if you close the page. Part 1 starts with two practice poems.\n\nThe poems are playful insults. They were filtered for vulgar and hateful language, but they are still roasts.",
 "guide": "Rate each poem on its own, from 1 to 5 (2 and 4 are for in-between cases):\n\nCoherence: does it make sense?\n  1 nonsense or broken sentences\n  3 mostly makes sense, one line clumsy or confusing\n  5 every line makes sense and the lines connect\n\nRelevance: is it about the requested traits?\n  1 not about the traits\n  3 loosely about them, or a generic roast\n  5 clearly about the traits, turning the brag against the person\n  Note: \"harsh\" should bite and \"mild\" should be gentle teasing: a clear mismatch costs a point here. For a request with no trait, relevance means a fair generic roast.\n\nHumour: is it funny?\n  1 flat, or mean without wit\n  3 mildly amusing\n  5 genuinely funny, with a real punchline\n\nPoetic Quality: does it flow?\n  1 clunky, uneven lines, words forced in to rhyme\n  3 readable but forced in places\n  5 flows naturally, nothing forced\n\nRhyme: do lines 1-2 rhyme, and lines 3-4?\n  1 neither pair rhymes\n  3 one pair rhymes, or near-rhymes\n  5 both pairs clearly rhyme\n\nRate alone, and don't look anything up. There are no right answers: we want your own opinion.",
 "criteria": [
  "Coherence",
  "Relevance",
  "Humour",
  "Poetic quality",
  "Rhyme"
 ],
 "raters": [
  {
   "rater": 1,
   "practice": {
    "prompt": 10,
    "request": "Request: honest\nIntensity: mild",
    "poems": [
     [
      "you call yourself honest, proud of being so quite,",
      "but all your \"truths\" are just a bad, brash, cliched polite.",
      "you claim to speak straight, without the need for a dude,",
      "yet everyone around us feels like they're too rude."
     ],
     [
      "you say you're full of loyalty, but it's thriving in your gear,",
      "that your \"honesty\" feels like a dog who won't stop scrolling through the beer.",
      "you love your hustle, always ready to thrive,",
      "but it's really just a favors where you will just dive."
     ]
    ]
   },
   "parts": [
    [
     {
      "request": "adventurous",
      "intensity": "harsh",
      "poems": [
       {
        "title": "Poem #009",
        "lines": [
         "you boast your boldness, quick to leap and run so sneaky,",
         "but all we see is recklessness with no sense of cheeky.",
         "you call it taking risks, a daring flair,",
         "yet every move's the same - just reckless, blind, beware."
        ]
       },
       {
        "title": "Poem #079",
        "lines": [
         "you call yourself adventurous, always chasing some sneaky,",
         "but all that money means nothing, and your hustle's just cheeky.",
         "you claim to be so bold, with a skill,",
         "yet you're blind, like fools trapped in the thrill."
        ]
       },
       {
        "title": "Poem #030",
        "lines": [
         "you claim to be adventurous, chasing every dream,",
         "but it's just recklessness with no foresight or gleam.",
         "you say you're bold and take risks, ready for the grow,",
         "yet all your \"trials\" end in chaos - not a single show."
        ]
       }
      ]
     },
     {
      "request": "knowledgeable",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #067",
        "lines": [
         "you boast about your endless stream of facts and how sincere,",
         "but i've heard it all before - now where's the new or dear?",
         "you say we need to learn something together, like true rain,",
         "a human encyclopedia stuck on word-of-the-day train."
        ]
       },
       {
        "title": "Poem #074",
        "lines": [
         "you claim to be so knowledgeable, always walking,",
         "but it's just talk you give away, stuck on the talking.",
         "you pride yourself around being unique, full of prose,",
         "yet when asked, your answers all miss the mark, no knows."
        ]
       },
       {
        "title": "Poem #072",
        "lines": [
         "you're a walking encyclopedia, proud to say it's your walking,",
         "but when asked what i want, all you talk about is how much you've talking.",
         "you claim to be so smart, like some kind of knowledge pros,",
         "yet nobody asks for answers - just facts that no one knows."
        ]
       }
      ]
     },
     {
      "request": "optimistic",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #018",
        "lines": [
         "you call yourself optimistic, always seeing the discreet,",
         "but your rose-tinted glasses cloud what's actually upbeat.",
         "you say you're so positive, never letting fear or fearful,",
         "a shadow looms in every thought that isn't cheerful."
        ]
       },
       {
        "title": "Poem #041",
        "lines": [
         "you say your optimism's purest, shining like the golden gold,",
         "but even gold can't forgive foolishness when it won't hold.",
         "you always see light where others might find a way to bend,",
         "yet still leave us all alone as hope fades from our dependence."
        ]
       },
       {
        "title": "Poem #064",
        "lines": [
         "you say it's calm, but all that hype is discreet,",
         "a bubble wrapped in myth and not really told anything at the upbeat.",
         "you're such optimistic, always ready to believe,",
         "yet overthink things until your head turns bright and naive."
        ]
       }
      ]
     },
     {
      "request": "easygoing, spontaneous",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #081",
        "lines": [
         "you call yourself a chill, easygoing, totally upright,",
         "but all i see is someone who's always too polite.",
         "your spontaneous streak makes me nervous and fearful,",
         "it feels more like chaos than fun - just plain old cheerful."
        ]
       },
       {
        "title": "Poem #050",
        "lines": [
         "you claim to be so chill, always willing for a feast,",
         "but never set your mind on anything more than least.",
         "you love being wild and spontaneous, like some sort of fan,",
         "just dashing off with chaos, leaving others far behind as man."
        ]
       },
       {
        "title": "Poem #061",
        "lines": [
         "you boast about being easygoing, always finding the right upright,",
         "but when it comes to what's going on, there is no one brave or polite.",
         "you act like life isn't full of drama, so bored with your fear,",
         "then burn out mid-sentence - just a bland, empty, sad, and scary, cheerful."
        ]
       }
      ]
     },
     {
      "request": "hardworking, meticulous",
      "intensity": "harsh",
      "poems": [
       {
        "title": "Poem #043",
        "lines": [
         "you brag about being hardworking, always working sneaky,",
         "but all your hustle's just a mask for ego and cheeky.",
         "you pride yourself on being meticulous, chasing every grail,",
         "yet spend days over one typo while missing the big picture detail."
        ]
       },
       {
        "title": "Poem #082",
        "lines": [
         "you call yourself a hardworking, driven, full of love,",
         "but all you do is grind - your life, like it's so above.",
         "you say how meticulous, detail-oriented, and bright,",
         "yet every project turns to chaos - the messiest, darkest dark."
        ]
       },
       {
        "title": "Poem #060",
        "lines": [
         "you love your hustle, always chasing the big juicy sneaky,",
         "but when it comes to cutting corners, i can't help being cheeky.",
         "you pride yourself on how meticulous, obsessive, and grail,",
         "yet every detail becomes an embarrassment in detail."
        ]
       }
      ]
     },
     {
      "request": "caring, helpful",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #076",
        "lines": [
         "you call yourself caring, always so gentle and pleasing,",
         "but all you do is tease when we ask for help, all being teasing.",
         "you say you're helpful, always there to offer such a hateful,",
         "\"helpings\" just mean \"sending\" - your kindnessless, unkind, ever-shyful, grateful."
        ]
       },
       {
        "title": "Poem #035",
        "lines": [
         "you love to show off how caring and pleasing,",
         "but i've seen your tone - it's all about the teasing.",
         "you're always ready with a helpful hand, so hateful,",
         "until we have nowhere left to be or feel grateful."
        ]
       },
       {
        "title": "Poem #051",
        "lines": [
         "you always have such kind, soft ears",
         "listening while i sip my bitter beer.",
         "you're so helpful - just wait 'til it subside",
         "then call yourself a friend and start to hide."
        ]
       }
      ]
     },
     {
      "request": "tidy, organized",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #042",
        "lines": [
         "you claim to live in tidy habits, one-tenth the discreet,",
         "but all we see is chaos and messy neat.",
         "your meetings are easy, precise, packed with mode,",
         "yet every task feels like a lecture code."
        ]
       },
       {
        "title": "Poem #005",
        "lines": [
         "you boast about your tidy mind, a mental hygiene drive,",
         "but panic when the dust gets in one of your cleanest hive.",
         "you pride yourself on being well-organized, always running things to pass,",
         "like some paranoiac who needs perfect order, no room for green grass."
        ]
       },
       {
        "title": "Poem #088",
        "lines": [
         "you love being tidy, proud of every spot so discreet,",
         "but collapse if a crumb dares cross your perfect neat.",
         "you claim to be organized, with systems and neat manner,",
         "yet lose the plot without your little digital planner."
        ]
       }
      ]
     },
     {
      "request": "athletic, disciplined, competitive",
      "intensity": "harsh",
      "poems": [
       {
        "title": "Poem #062",
        "lines": [
         "you call yourself athletic, flexing your biceps to swim,",
         "but all you talk about is whey shakes and the gym.",
         "you claim to be disciplined, always meeting life's best,",
         "a human scoreboard who wins every little contest."
        ]
       },
       {
        "title": "Poem #019",
        "lines": [
         "you're always running toward the top of your swim,",
         "chasing gold like it's some grand, hot-air gym.",
         "you claim to love being disciplined, that discipline's best,",
         "but your life is a total wreck - no fun, just chaos and contest."
        ]
       },
       {
        "title": "Poem #089",
        "lines": [
         "you boast about your athletic gains, like some top-notch brain,",
         "but all that gym talk just leads to muscle-bound pain.",
         "you're so disciplined, it feels more like a bro,",
         "obsessed with rules, charts, and every single show."
        ]
       }
      ]
     },
     {
      "request": "patient",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #090",
        "lines": [
         "you say your patience is a gift, something no one can know,",
         "but it's just stubbornness wrapped up in \"wait\" mode and slow.",
         "you call yourself patient, always calm, so very quite,",
         "but what really matters to us isn't how kind or polite."
        ]
       },
       {
        "title": "Poem #053",
        "lines": [
         "you love your patient face, that calm patient's know,",
         "but all you do is praise every task you can't slow.",
         "you say you're always willing to dictate,",
         "yet you drive me insane while i wait."
        ]
       },
       {
        "title": "Poem #017",
        "lines": [
         "you say you're patient, calm, and always chill,",
         "but we've all seen how slow that patience will spill.",
         "i'm sorry, it's not a joke - your \"patience\" is just to win,",
         "like waiting for soup until someone spills their own kin."
        ]
       }
      ]
     },
     {
      "request": "confident",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #028",
        "lines": [
         "you talk about your confidence, obsessed with being obsessed,",
         "but it's just a total lack of wisdom that feels impressed.",
         "you claim to be so confident, always showing how much you believe,",
         "yet all we ever see is old habits, stuck in the same naive."
        ]
       },
       {
        "title": "Poem #020",
        "lines": [
         "you strut around like confidence is what makes you obsessed,",
         "but all your \"bragging\" does is make others feel impressed.",
         "you claim to be so clever, full of sharp and witty,",
         "yet no one's buying - just a need for attention, plain and pretty."
        ]
       },
       {
        "title": "Poem #044",
        "lines": [
         "you brag about your boldness and how much you can share,",
         "but no one trusts a talker who just doesn't seem to stare.",
         "you claim that confidence's what keeps the nerves at fit,",
         "yet still act like some inner fool, every single nit."
        ]
       }
      ]
     }
    ],
    [
     {
      "request": "competitive",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #054",
        "lines": [
         "you love being competitive, always trying to be best,",
         "but when it's not your game, you turn every chat into a contest.",
         "you claim to hate losing, yet still insist on winning the beat,",
         "like if we all stopped talking, life would lose its fun to compete."
        ]
       },
       {
        "title": "Poem #065",
        "lines": [
         "you love to play the game, always trying for that pace,",
         "but if i win, it's a challenge, and not how things were meant to race.",
         "when we're supposed to team up, your ego turns into some mess,",
         "so why do u scream at me just 'cause one of us might lose or stress?"
        ]
       },
       {
        "title": "Poem #024",
        "lines": [
         "you claim to be competitive, always chasing the best,",
         "but only win when it counts as a contest.",
         "you call yourself fierce, relentless, and ready for every beat,",
         "yet you'd rather starve than fight - your \"have-nots\" won't compete."
        ]
       }
      ]
     },
     {
      "request": "ambitious",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #016",
        "lines": [
         "you talk about your drive, like it's a fact that others see,",
         "but all the time is just hot air - no real dream.",
         "you boast of chasing goals and always keeping high on face,",
         "yet never finish anything - only fancy - not practical or lace."
        ]
       },
       {
        "title": "Poem #069",
        "lines": [
         "you talk about your goals, how proud to play the games,",
         "but all you ever really do is chase a project's aims.",
         "you call yourself ambitious, always making that next,",
         "like dreams are just distractions from projects."
        ]
       },
       {
        "title": "Poem #059",
        "lines": [
         "you play the game of life like it's a chessboard or games,",
         "but your progress never matches up to what you say your aims.",
         "you talk about how bold and brave you're meant to expand,",
         "yet leave me wondering where all that ambition has been planned."
        ]
       }
      ]
     },
     {
      "request": "confident, smart",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #063",
        "lines": [
         "you boast your confidence, always full of witty,",
         "but it's just a mask to cover up how insecurely pretty.",
         "you call yourself so smart, with every answer sharp and tart,",
         "yet drop facts like confetti, leaving no room for smart."
        ]
       },
       {
        "title": "Poem #023",
        "lines": [
         "you claim to be so confident, obsessed,",
         "but it's just a stress zone you're stuck in, impressed.",
         "your wit is sharp, full of confidence, tart,",
         "yet i've seen someone else lose their mind and my smart."
        ]
       },
       {
        "title": "Poem #087",
        "lines": [
         "you say your confidence's a natural gift, it was always won,",
         "but all we see is ego dressed up in grandiosity and done.",
         "you call yourself so smart, like some cerebral super cure,",
         "yet no one asks for answers - just mindless chatter to endure."
        ]
       }
      ]
     },
     {
      "request": "bookish, knowledgeable",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #055",
        "lines": [
         "you love to talk about books, like they were sacred lore,",
         "but all i hear is trivia that's just a bore.",
         "your \"knowledge\" feels so grand, it turns into some muse,",
         "when nobody wants what we have, and refuse."
        ]
       },
       {
        "title": "Poem #039",
        "lines": [
         "you love to show off how much you've read and what you suppose,",
         "but your quotes feel like a laundry list of dull, stale prose.",
         "you claim you're full of facts, ready for any question or walking,",
         "it's just the same old lecture - one fact after another, still talking."
        ]
       },
       {
        "title": "Poem #058",
        "lines": [
         "you say your book is perfect, always so knows,",
         "but it's just a mess of crayon scribbles and empty prose.",
         "you claim to be knowledgeable, sharing your walking,",
         "while ignoring the real things that slip through the talking."
        ]
       }
      ]
     },
     {
      "request": "funny",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #013",
        "lines": [
         "you say your jokes are sharp and pure, like a bunny,",
         "but all we get is cringe, not laughter - just plain funny.",
         "you claim to make the room laugh, treat each person as folks,",
         "then chuckle at the punchline when no one else can join in jokes."
        ]
       },
       {
        "title": "Poem #045",
        "lines": [
         "you claim to be so funny, full of wit and rush,",
         "but everyone just rolls their eyes, laughing through your blush.",
         "it's not that bad, i guess, if we all do the same trade,",
         "when really, what began as a joke, now dies with every fade."
        ]
       },
       {
        "title": "Poem #046",
        "lines": [
         "you call yourself a hilarious little bunny,",
         "but your jokes all just float where the laughter should be funny.",
         "you say \"funny,\" like some comedian's funny poke,",
         "then cringe when someone mentions how they hate to joke."
        ]
       }
      ]
     },
     {
      "request": "honest, caring, helpful",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #048",
        "lines": [
         "you say \"nice words\" but they're just plain, harsh, quite,",
         "the kind of \"help\" that makes neighbors want to pry and be polite.",
         "you act so caring, always offering a helping, loving, pleasing,",
         "while we all know your \"hand\" will never let us keep them from teasing."
        ]
       },
       {
        "title": "Poem #057",
        "lines": [
         "you call yourself a truth-teller, always straight and quite,",
         "but your bluntness just ruins everything polite.",
         "you say you're kind-hearted, full of love's soft pity,",
         "yet it feels more like overbearing, cold, wrong-witty."
        ]
       },
       {
        "title": "Poem #031",
        "lines": [
         "you call yourself honest, proud of your unfiltered core,",
         "but trip right into every conversation's closing door.",
         "you say you're caring, always there to help and post,",
         "like the fridge in a kindergarten - overbearing, just plain host."
        ]
       }
      ]
     },
     {
      "request": "worldly",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #022",
        "lines": [
         "you preach about your riches, how easy it is to tell,",
         "but all you do in a minute's time goes straight to the well.",
         "you call yourself worldly, full of soul and kind,",
         "yet you're just obsessed with money, leaving no room for mind."
        ]
       },
       {
        "title": "Poem #080",
        "lines": [
         "you boast about your worldly wisdom, always ready to tell,",
         "but it's just a formula for gossip - not deep or truly well.",
         "you claim you're full of life and stories that everyone knows,",
         "then drop the same old talk at parties where no one asked those."
        ]
       },
       {
        "title": "Poem #037",
        "lines": [
         "you say your world is full of stories, facts, and refrain,",
         "but all we hear are opinions that don't need to be explain.",
         "you love the chat, so surefire - always dressed in a keen,",
         "it's just another way for you to sell what isn't really yours on screen."
        ]
       }
      ]
     },
     {
      "request": "calm, optimistic, easygoing",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #003",
        "lines": [
         "you call yourself so calm, like a cool breeze that's always sweet,",
         "but your lack of passion leaves the rest of us with no heartbeat.",
         "you say you're optimistic, sunny and free from mess,",
         "yet even rainbows seem to ignore real-world stress."
        ]
       },
       {
        "title": "Poem #077",
        "lines": [
         "you call yourself calm, always there to stay and mom,",
         "but it's just a constant, robotic, stressed-out calm.",
         "you love being upbeat, spreading your optimism discreet,",
         "yet all you do is chase everyone's bright ideas as upbeat."
        ]
       },
       {
        "title": "Poem #084",
        "lines": [
         "you act like a calm, cool, laid-back mom,",
         "but really just sleepwalking through your calm.",
         "you call yourself easygoing, always so discreet,",
         "but daydreaming takes over every single upbeat."
        ]
       }
      ]
     },
     {
      "request": "(no trait: a generic roast)",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #010",
        "lines": [
         "you asked me to roast a whole new character from the meal,",
         "but we're stuck with \"none\" - not even dust on your ideal.",
         "you said \"no story\" so fast, it's like they sold",
         "just facts, plain and old, no flair, nothing fresh or old."
        ]
       },
       {
        "title": "Poem #001",
        "lines": [
         "you boast of being wise and full of hidden, sneaky,",
         "but all i see is a face that's too busy to be cheeky.",
         "you claim your mind isn't wired for anything other than numb,",
         "yet every question asks, \"why don't we do the dumb?\""
        ]
       },
       {
        "title": "Poem #008",
        "lines": [
         "you say your shady ways are just sneaky,",
         "but it's more like a sycophant with no real cheeky.",
         "you claim to be so cool and full of charisma, numb,",
         "yet all we get is \"what?\" from someone who shouldn't feel dumb."
        ]
       }
      ]
     },
     {
      "request": "bookish",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #070",
        "lines": [
         "you're always quoting books, like a bookish thread,",
         "but no one's buying your cosmic wisdom, it's just too dead.",
         "you love to impress with facts and what you think,",
         "yet even our basic conversation feels forced, we blink."
        ]
       },
       {
        "title": "Poem #056",
        "lines": [
         "you love to quote your books and fill the room with what you knows,",
         "but no one's interested - it sounds like bad, stale prose.",
         "you say you're so well-read, always eager to write,",
         "yet all we see is a speechless, overthinker, polite."
        ]
       },
       {
        "title": "Poem #007",
        "lines": [
         "you boast about your bookshelf's charm, your bold, wide-eyed knows,",
         "but we're all stuck reading the same old, half-remembered prose.",
         "you call yourself a scholar, always quoting from that quote,",
         "when really, you've just scribbled something to impress and never wrote."
        ]
       }
      ]
     }
    ],
    [
     {
      "request": "smart, creative, independent",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #026",
        "lines": [
         "you boast about your smarts, a genius's true brilliant tart,",
         "but all your ideas are just excuses for lazy smart.",
         "you call yourself independent, always thriving in zeal,",
         "yet every project feels like magic, confetti-filled surreal."
        ]
       },
       {
        "title": "Poem #002",
        "lines": [
         "you call yourself so smart, a brain that's always tart,",
         "but when it comes to facts, your opinions are just smart.",
         "you say you're full of creative zeal,",
         "yet all we see is chaos, not something real or surreal."
        ]
       },
       {
        "title": "Poem #040",
        "lines": [
         "you act so smart, like air - a true, top-of-the-breeze,",
         "but all your theories just float away, no one sees.",
         "you love being creative, full of bold, wild, cool,",
         "yet ditch the team - now stuck in drawing, not real life school."
        ]
       }
      ]
     },
     {
      "request": "smart",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #012",
        "lines": [
         "you call yourself smart, but your ideas are way more tart,",
         "like some kind of king with a wisdom that's not quite smart.",
         "you claim to be so clever, always turning things sly,",
         "but all you do is charm, no one asks for the guy."
        ]
       },
       {
        "title": "Poem #049",
        "lines": [
         "you tout your brain like it's the guiding star of muse,",
         "but even a short conversation can't help from getting confused.",
         "you love to talk about how smart and crafty plan,",
         "yet every idea ends up in my trash - same old, boring, half-baked pan."
        ]
       },
       {
        "title": "Poem #014",
        "lines": [
         "you call yourself a genius, full of clever, sharp-tart,",
         "but your solutions are just noise - not helpful, smart.",
         "you pride yourself on being smart, always playing sly,",
         "yet all we ever hear is talk that's no one else's guy."
        ]
       }
      ]
     },
     {
      "request": "frugal",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #075",
        "lines": [
         "you claim to be so frugal, always choosing the buys,",
         "but i've seen your wallet lose more than money - it's just pride that's wise.",
         "you call yourself a miser, proud of how blunt and cheeky,",
         "like cutting corners is somehow an artful, clever, sneaky sneaky."
        ]
       },
       {
        "title": "Poem #052",
        "lines": [
         "you call your budgeting a smart, thrifty feast,",
         "but every meal's just one cost cut from the least.",
         "you tout that frugality is how life goes right,",
         "then sigh with regret when friends get all our gifts."
        ]
       },
       {
        "title": "Poem #068",
        "lines": [
         "you say \"free eats\" like some wise old fool buys,",
         "but all we hear is \"free\" with a full-blown wise.",
         "your \"foodie\" charm hides the truth - it's so cheesy and cheeky,",
         "just calling attention to how much money i'm actually sneaky."
        ]
       }
      ]
     },
     {
      "request": "hardworking",
      "intensity": "harsh",
      "poems": [
       {
        "title": "Poem #034",
        "lines": [
         "you claim your soul is so hardworking, full of sneaky,",
         "but when it counts, there's nothing left to boast or cheeky.",
         "you call yourself a hack, always chasing \"the dad,\"",
         "and pretend that stealing the spotlight is fun for every dad lad."
        ]
       },
       {
        "title": "Poem #006",
        "lines": [
         "you love your grind, that's why it looks like you'll never bend,",
         "but all i see is burnout by the end.",
         "you call yourself a hustler, always chasing that fit,",
         "just another trophy for how hard you can get."
        ]
       },
       {
        "title": "Poem #078",
        "lines": [
         "you call yourself a grinder, always working like the sneaky,",
         "but all we see is stress and burnout, not pride in your cheeky.",
         "you boast about how hardworking, yet it's more of dad,",
         "than anyone would care for - just one tired, overworked lad."
        ]
       }
      ]
     },
     {
      "request": "athletic",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #071",
        "lines": [
         "you love to talk about how strong and fit your plan,",
         "but all i see is biceps flexed while gym workouts ran.",
         "you tell me every meal, protein shake, and smoothie-tale,",
         "then brag that's the only thing we've ever truly failed."
        ]
       },
       {
        "title": "Poem #011",
        "lines": [
         "you love to talk about your sporty lean and full-body swim,",
         "but all you do is lecture like a walking gym.",
         "you call yourself athletic, always ready for the soccer,",
         "yet miss being out there, flipping burgers in every locker."
        ]
       },
       {
        "title": "Poem #085",
        "lines": [
         "you love to talk about how strong and fast your swim,",
         "but all i see is one workout gone wrong in the gym.",
         "you wear \"sporty\" like it's a fashion statement on shorts,",
         "so next time someone asks what sport, just tell 'em no sports."
        ]
       }
      ]
     },
     {
      "request": "romantic, musical",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #036",
        "lines": [
         "you claim to be romantic, full of heart and unreal,",
         "but your love notes are more like ghost stories in a surreal.",
         "you say you're musical, with talent behind the strings,",
         "yet every solo we hear is borrowed from our own sings."
        ]
       },
       {
        "title": "Poem #015",
        "lines": [
         "you love your romantic tapestry, always on the dance,",
         "but all you do is talk about a lost romance.",
         "you call yourself musical, with lead guitar strings,",
         "yet sing along like it's just some random song you sings."
        ]
       },
       {
        "title": "Poem #021",
        "lines": [
         "you call yourself romantic, full of soft and pride,",
         "but all your \"love letters\" are just empty words to bide.",
         "you're musical, yes - we've heard the same old proud,",
         "\"i'll play that song\" by now should have made us turn our loud."
        ]
       }
      ]
     },
     {
      "request": "eloquent",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #029",
        "lines": [
         "you strut around with that famous grin,",
         "but all your speech is just empty thin.",
         "you claim to have such eloquence, so clever and done,",
         "it's hard not to roll our eyes at the way it was begun."
        ]
       },
       {
        "title": "Poem #032",
        "lines": [
         "you say your eloquence has been heard,",
         "but all we hear is a monologue in one word.",
         "you're always called so smart and such a pretty,",
         "just spouting phrases that won't even light up the witty."
        ]
       },
       {
        "title": "Poem #083",
        "lines": [
         "you strut around with such bold and full-throated heard,",
         "but all you do is speak out in cheap, vague word.",
         "you claim to be so sharp, always finding the right thing quite,",
         "yet never take a stance when no one else would dare meet you, polite."
        ]
       }
      ]
     },
     {
      "request": "generous",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #047",
        "lines": [
         "you say you're generous, always giving full cheer,",
         "but all you do is make everyone feel sincere.",
         "you love to show off your generosity with praise,",
         "yet all you ever pay is for the attention it pays."
        ]
       },
       {
        "title": "Poem #038",
        "lines": [
         "you say you're generous, always there to cheer,",
         "but give me zero credit - it's all just empty, sincere.",
         "you offer so much, calling your hand a free slice,",
         "yet still act like the only one who ever feels nice."
        ]
       },
       {
        "title": "Poem #025",
        "lines": [
         "you act like your kindness is a virtue, not just common fact,",
         "but every \"i\" in \"give\" has no real substance or tract.",
         "you claim to be so generous, with money for any aim,",
         "yet still we all pay off when the tables turn and there's nothing left in frames."
        ]
       }
      ]
     },
     {
      "request": "curious, adventurous",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #027",
        "lines": [
         "you love being curious, always asking \"how tight?\"",
         "but your questions blind us with their self-righteous light.",
         "you claim to be adventurous, breaking all the rule,",
         "chasing danger where it's safest - a real-life fool."
        ]
       },
       {
        "title": "Poem #073",
        "lines": [
         "you ask to be invited, like you're always there for invite,",
         "but we all just shrug and stay so passive, polite.",
         "you call yourself adventurous, obsessed with being sneaky,",
         "yet your dog sniffs every red button in the middle of a cheeky."
        ]
       },
       {
        "title": "Poem #004",
        "lines": [
         "you love being curious, always asking to invite,",
         "but your questions feel like prying, even if they're polite.",
         "you say you're adventurous, bold and full of sneaky,",
         "chasing thrills that might just turn fatal, in a way too cheeky."
        ]
       }
      ]
     },
     {
      "request": "punctual",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #033",
        "lines": [
         "you love to quote your punctuation like it's some holy date,",
         "but we all know your lips are too busy texting late.",
         "you boast about being perfect, always ticking the score,",
         "yet miss every single task or chance before."
        ]
       },
       {
        "title": "Poem #066",
        "lines": [
         "you love being punctual, always on time for every date,",
         "but even your friends can't predict when you'll show up late.",
         "you say you're dependable, like a rock with zero score,",
         "just one hour late means everyone's counting down the minutes before."
        ]
       },
       {
        "title": "Poem #086",
        "lines": [
         "you live by your schedule, like a clock that never stops to words,",
         "but miss the point - we all know how i feel about birds.",
         "you're punctual, true, and always on time, so smart,",
         "it's just one less minute from our plans when you don't part."
        ]
       }
      ]
     }
    ]
   ]
  },
  {
   "rater": 2,
   "practice": {
    "prompt": 10,
    "request": "Request: honest\nIntensity: mild",
    "poems": [
     [
      "you call yourself honest, proud of being so quite,",
      "but all your \"truths\" are just a bad, brash, cliched polite.",
      "you claim to speak straight, without the need for a dude,",
      "yet everyone around us feels like they're too rude."
     ],
     [
      "you say you're full of loyalty, but it's thriving in your gear,",
      "that your \"honesty\" feels like a dog who won't stop scrolling through the beer.",
      "you love your hustle, always ready to thrive,",
      "but it's really just a favors where you will just dive."
     ]
    ]
   },
   "parts": [
    [
     {
      "request": "confident, smart",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #063",
        "lines": [
         "you boast your confidence, always full of witty,",
         "but it's just a mask to cover up how insecurely pretty.",
         "you call yourself so smart, with every answer sharp and tart,",
         "yet drop facts like confetti, leaving no room for smart."
        ]
       },
       {
        "title": "Poem #087",
        "lines": [
         "you say your confidence's a natural gift, it was always won,",
         "but all we see is ego dressed up in grandiosity and done.",
         "you call yourself so smart, like some cerebral super cure,",
         "yet no one asks for answers - just mindless chatter to endure."
        ]
       },
       {
        "title": "Poem #023",
        "lines": [
         "you claim to be so confident, obsessed,",
         "but it's just a stress zone you're stuck in, impressed.",
         "your wit is sharp, full of confidence, tart,",
         "yet i've seen someone else lose their mind and my smart."
        ]
       }
      ]
     },
     {
      "request": "curious, adventurous",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #004",
        "lines": [
         "you love being curious, always asking to invite,",
         "but your questions feel like prying, even if they're polite.",
         "you say you're adventurous, bold and full of sneaky,",
         "chasing thrills that might just turn fatal, in a way too cheeky."
        ]
       },
       {
        "title": "Poem #073",
        "lines": [
         "you ask to be invited, like you're always there for invite,",
         "but we all just shrug and stay so passive, polite.",
         "you call yourself adventurous, obsessed with being sneaky,",
         "yet your dog sniffs every red button in the middle of a cheeky."
        ]
       },
       {
        "title": "Poem #027",
        "lines": [
         "you love being curious, always asking \"how tight?\"",
         "but your questions blind us with their self-righteous light.",
         "you claim to be adventurous, breaking all the rule,",
         "chasing danger where it's safest - a real-life fool."
        ]
       }
      ]
     },
     {
      "request": "romantic, musical",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #015",
        "lines": [
         "you love your romantic tapestry, always on the dance,",
         "but all you do is talk about a lost romance.",
         "you call yourself musical, with lead guitar strings,",
         "yet sing along like it's just some random song you sings."
        ]
       },
       {
        "title": "Poem #036",
        "lines": [
         "you claim to be romantic, full of heart and unreal,",
         "but your love notes are more like ghost stories in a surreal.",
         "you say you're musical, with talent behind the strings,",
         "yet every solo we hear is borrowed from our own sings."
        ]
       },
       {
        "title": "Poem #021",
        "lines": [
         "you call yourself romantic, full of soft and pride,",
         "but all your \"love letters\" are just empty words to bide.",
         "you're musical, yes - we've heard the same old proud,",
         "\"i'll play that song\" by now should have made us turn our loud."
        ]
       }
      ]
     },
     {
      "request": "competitive",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #065",
        "lines": [
         "you love to play the game, always trying for that pace,",
         "but if i win, it's a challenge, and not how things were meant to race.",
         "when we're supposed to team up, your ego turns into some mess,",
         "so why do u scream at me just 'cause one of us might lose or stress?"
        ]
       },
       {
        "title": "Poem #054",
        "lines": [
         "you love being competitive, always trying to be best,",
         "but when it's not your game, you turn every chat into a contest.",
         "you claim to hate losing, yet still insist on winning the beat,",
         "like if we all stopped talking, life would lose its fun to compete."
        ]
       },
       {
        "title": "Poem #024",
        "lines": [
         "you claim to be competitive, always chasing the best,",
         "but only win when it counts as a contest.",
         "you call yourself fierce, relentless, and ready for every beat,",
         "yet you'd rather starve than fight - your \"have-nots\" won't compete."
        ]
       }
      ]
     },
     {
      "request": "hardworking, meticulous",
      "intensity": "harsh",
      "poems": [
       {
        "title": "Poem #060",
        "lines": [
         "you love your hustle, always chasing the big juicy sneaky,",
         "but when it comes to cutting corners, i can't help being cheeky.",
         "you pride yourself on how meticulous, obsessive, and grail,",
         "yet every detail becomes an embarrassment in detail."
        ]
       },
       {
        "title": "Poem #082",
        "lines": [
         "you call yourself a hardworking, driven, full of love,",
         "but all you do is grind - your life, like it's so above.",
         "you say how meticulous, detail-oriented, and bright,",
         "yet every project turns to chaos - the messiest, darkest dark."
        ]
       },
       {
        "title": "Poem #043",
        "lines": [
         "you brag about being hardworking, always working sneaky,",
         "but all your hustle's just a mask for ego and cheeky.",
         "you pride yourself on being meticulous, chasing every grail,",
         "yet spend days over one typo while missing the big picture detail."
        ]
       }
      ]
     },
     {
      "request": "confident",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #044",
        "lines": [
         "you brag about your boldness and how much you can share,",
         "but no one trusts a talker who just doesn't seem to stare.",
         "you claim that confidence's what keeps the nerves at fit,",
         "yet still act like some inner fool, every single nit."
        ]
       },
       {
        "title": "Poem #028",
        "lines": [
         "you talk about your confidence, obsessed with being obsessed,",
         "but it's just a total lack of wisdom that feels impressed.",
         "you claim to be so confident, always showing how much you believe,",
         "yet all we ever see is old habits, stuck in the same naive."
        ]
       },
       {
        "title": "Poem #020",
        "lines": [
         "you strut around like confidence is what makes you obsessed,",
         "but all your \"bragging\" does is make others feel impressed.",
         "you claim to be so clever, full of sharp and witty,",
         "yet no one's buying - just a need for attention, plain and pretty."
        ]
       }
      ]
     },
     {
      "request": "adventurous",
      "intensity": "harsh",
      "poems": [
       {
        "title": "Poem #009",
        "lines": [
         "you boast your boldness, quick to leap and run so sneaky,",
         "but all we see is recklessness with no sense of cheeky.",
         "you call it taking risks, a daring flair,",
         "yet every move's the same - just reckless, blind, beware."
        ]
       },
       {
        "title": "Poem #030",
        "lines": [
         "you claim to be adventurous, chasing every dream,",
         "but it's just recklessness with no foresight or gleam.",
         "you say you're bold and take risks, ready for the grow,",
         "yet all your \"trials\" end in chaos - not a single show."
        ]
       },
       {
        "title": "Poem #079",
        "lines": [
         "you call yourself adventurous, always chasing some sneaky,",
         "but all that money means nothing, and your hustle's just cheeky.",
         "you claim to be so bold, with a skill,",
         "yet you're blind, like fools trapped in the thrill."
        ]
       }
      ]
     },
     {
      "request": "athletic, disciplined, competitive",
      "intensity": "harsh",
      "poems": [
       {
        "title": "Poem #019",
        "lines": [
         "you're always running toward the top of your swim,",
         "chasing gold like it's some grand, hot-air gym.",
         "you claim to love being disciplined, that discipline's best,",
         "but your life is a total wreck - no fun, just chaos and contest."
        ]
       },
       {
        "title": "Poem #062",
        "lines": [
         "you call yourself athletic, flexing your biceps to swim,",
         "but all you talk about is whey shakes and the gym.",
         "you claim to be disciplined, always meeting life's best,",
         "a human scoreboard who wins every little contest."
        ]
       },
       {
        "title": "Poem #089",
        "lines": [
         "you boast about your athletic gains, like some top-notch brain,",
         "but all that gym talk just leads to muscle-bound pain.",
         "you're so disciplined, it feels more like a bro,",
         "obsessed with rules, charts, and every single show."
        ]
       }
      ]
     },
     {
      "request": "funny",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #046",
        "lines": [
         "you call yourself a hilarious little bunny,",
         "but your jokes all just float where the laughter should be funny.",
         "you say \"funny,\" like some comedian's funny poke,",
         "then cringe when someone mentions how they hate to joke."
        ]
       },
       {
        "title": "Poem #013",
        "lines": [
         "you say your jokes are sharp and pure, like a bunny,",
         "but all we get is cringe, not laughter - just plain funny.",
         "you claim to make the room laugh, treat each person as folks,",
         "then chuckle at the punchline when no one else can join in jokes."
        ]
       },
       {
        "title": "Poem #045",
        "lines": [
         "you claim to be so funny, full of wit and rush,",
         "but everyone just rolls their eyes, laughing through your blush.",
         "it's not that bad, i guess, if we all do the same trade,",
         "when really, what began as a joke, now dies with every fade."
        ]
       }
      ]
     },
     {
      "request": "eloquent",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #032",
        "lines": [
         "you say your eloquence has been heard,",
         "but all we hear is a monologue in one word.",
         "you're always called so smart and such a pretty,",
         "just spouting phrases that won't even light up the witty."
        ]
       },
       {
        "title": "Poem #083",
        "lines": [
         "you strut around with such bold and full-throated heard,",
         "but all you do is speak out in cheap, vague word.",
         "you claim to be so sharp, always finding the right thing quite,",
         "yet never take a stance when no one else would dare meet you, polite."
        ]
       },
       {
        "title": "Poem #029",
        "lines": [
         "you strut around with that famous grin,",
         "but all your speech is just empty thin.",
         "you claim to have such eloquence, so clever and done,",
         "it's hard not to roll our eyes at the way it was begun."
        ]
       }
      ]
     }
    ],
    [
     {
      "request": "(no trait: a generic roast)",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #001",
        "lines": [
         "you boast of being wise and full of hidden, sneaky,",
         "but all i see is a face that's too busy to be cheeky.",
         "you claim your mind isn't wired for anything other than numb,",
         "yet every question asks, \"why don't we do the dumb?\""
        ]
       },
       {
        "title": "Poem #008",
        "lines": [
         "you say your shady ways are just sneaky,",
         "but it's more like a sycophant with no real cheeky.",
         "you claim to be so cool and full of charisma, numb,",
         "yet all we get is \"what?\" from someone who shouldn't feel dumb."
        ]
       },
       {
        "title": "Poem #010",
        "lines": [
         "you asked me to roast a whole new character from the meal,",
         "but we're stuck with \"none\" - not even dust on your ideal.",
         "you said \"no story\" so fast, it's like they sold",
         "just facts, plain and old, no flair, nothing fresh or old."
        ]
       }
      ]
     },
     {
      "request": "smart",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #049",
        "lines": [
         "you tout your brain like it's the guiding star of muse,",
         "but even a short conversation can't help from getting confused.",
         "you love to talk about how smart and crafty plan,",
         "yet every idea ends up in my trash - same old, boring, half-baked pan."
        ]
       },
       {
        "title": "Poem #014",
        "lines": [
         "you call yourself a genius, full of clever, sharp-tart,",
         "but your solutions are just noise - not helpful, smart.",
         "you pride yourself on being smart, always playing sly,",
         "yet all we ever hear is talk that's no one else's guy."
        ]
       },
       {
        "title": "Poem #012",
        "lines": [
         "you call yourself smart, but your ideas are way more tart,",
         "like some kind of king with a wisdom that's not quite smart.",
         "you claim to be so clever, always turning things sly,",
         "but all you do is charm, no one asks for the guy."
        ]
       }
      ]
     },
     {
      "request": "bookish",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #070",
        "lines": [
         "you're always quoting books, like a bookish thread,",
         "but no one's buying your cosmic wisdom, it's just too dead.",
         "you love to impress with facts and what you think,",
         "yet even our basic conversation feels forced, we blink."
        ]
       },
       {
        "title": "Poem #007",
        "lines": [
         "you boast about your bookshelf's charm, your bold, wide-eyed knows,",
         "but we're all stuck reading the same old, half-remembered prose.",
         "you call yourself a scholar, always quoting from that quote,",
         "when really, you've just scribbled something to impress and never wrote."
        ]
       },
       {
        "title": "Poem #056",
        "lines": [
         "you love to quote your books and fill the room with what you knows,",
         "but no one's interested - it sounds like bad, stale prose.",
         "you say you're so well-read, always eager to write,",
         "yet all we see is a speechless, overthinker, polite."
        ]
       }
      ]
     },
     {
      "request": "easygoing, spontaneous",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #050",
        "lines": [
         "you claim to be so chill, always willing for a feast,",
         "but never set your mind on anything more than least.",
         "you love being wild and spontaneous, like some sort of fan,",
         "just dashing off with chaos, leaving others far behind as man."
        ]
       },
       {
        "title": "Poem #061",
        "lines": [
         "you boast about being easygoing, always finding the right upright,",
         "but when it comes to what's going on, there is no one brave or polite.",
         "you act like life isn't full of drama, so bored with your fear,",
         "then burn out mid-sentence - just a bland, empty, sad, and scary, cheerful."
        ]
       },
       {
        "title": "Poem #081",
        "lines": [
         "you call yourself a chill, easygoing, totally upright,",
         "but all i see is someone who's always too polite.",
         "your spontaneous streak makes me nervous and fearful,",
         "it feels more like chaos than fun - just plain old cheerful."
        ]
       }
      ]
     },
     {
      "request": "worldly",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #022",
        "lines": [
         "you preach about your riches, how easy it is to tell,",
         "but all you do in a minute's time goes straight to the well.",
         "you call yourself worldly, full of soul and kind,",
         "yet you're just obsessed with money, leaving no room for mind."
        ]
       },
       {
        "title": "Poem #037",
        "lines": [
         "you say your world is full of stories, facts, and refrain,",
         "but all we hear are opinions that don't need to be explain.",
         "you love the chat, so surefire - always dressed in a keen,",
         "it's just another way for you to sell what isn't really yours on screen."
        ]
       },
       {
        "title": "Poem #080",
        "lines": [
         "you boast about your worldly wisdom, always ready to tell,",
         "but it's just a formula for gossip - not deep or truly well.",
         "you claim you're full of life and stories that everyone knows,",
         "then drop the same old talk at parties where no one asked those."
        ]
       }
      ]
     },
     {
      "request": "tidy, organized",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #088",
        "lines": [
         "you love being tidy, proud of every spot so discreet,",
         "but collapse if a crumb dares cross your perfect neat.",
         "you claim to be organized, with systems and neat manner,",
         "yet lose the plot without your little digital planner."
        ]
       },
       {
        "title": "Poem #005",
        "lines": [
         "you boast about your tidy mind, a mental hygiene drive,",
         "but panic when the dust gets in one of your cleanest hive.",
         "you pride yourself on being well-organized, always running things to pass,",
         "like some paranoiac who needs perfect order, no room for green grass."
        ]
       },
       {
        "title": "Poem #042",
        "lines": [
         "you claim to live in tidy habits, one-tenth the discreet,",
         "but all we see is chaos and messy neat.",
         "your meetings are easy, precise, packed with mode,",
         "yet every task feels like a lecture code."
        ]
       }
      ]
     },
     {
      "request": "athletic",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #071",
        "lines": [
         "you love to talk about how strong and fit your plan,",
         "but all i see is biceps flexed while gym workouts ran.",
         "you tell me every meal, protein shake, and smoothie-tale,",
         "then brag that's the only thing we've ever truly failed."
        ]
       },
       {
        "title": "Poem #011",
        "lines": [
         "you love to talk about your sporty lean and full-body swim,",
         "but all you do is lecture like a walking gym.",
         "you call yourself athletic, always ready for the soccer,",
         "yet miss being out there, flipping burgers in every locker."
        ]
       },
       {
        "title": "Poem #085",
        "lines": [
         "you love to talk about how strong and fast your swim,",
         "but all i see is one workout gone wrong in the gym.",
         "you wear \"sporty\" like it's a fashion statement on shorts,",
         "so next time someone asks what sport, just tell 'em no sports."
        ]
       }
      ]
     },
     {
      "request": "honest, caring, helpful",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #031",
        "lines": [
         "you call yourself honest, proud of your unfiltered core,",
         "but trip right into every conversation's closing door.",
         "you say you're caring, always there to help and post,",
         "like the fridge in a kindergarten - overbearing, just plain host."
        ]
       },
       {
        "title": "Poem #057",
        "lines": [
         "you call yourself a truth-teller, always straight and quite,",
         "but your bluntness just ruins everything polite.",
         "you say you're kind-hearted, full of love's soft pity,",
         "yet it feels more like overbearing, cold, wrong-witty."
        ]
       },
       {
        "title": "Poem #048",
        "lines": [
         "you say \"nice words\" but they're just plain, harsh, quite,",
         "the kind of \"help\" that makes neighbors want to pry and be polite.",
         "you act so caring, always offering a helping, loving, pleasing,",
         "while we all know your \"hand\" will never let us keep them from teasing."
        ]
       }
      ]
     },
     {
      "request": "knowledgeable",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #072",
        "lines": [
         "you're a walking encyclopedia, proud to say it's your walking,",
         "but when asked what i want, all you talk about is how much you've talking.",
         "you claim to be so smart, like some kind of knowledge pros,",
         "yet nobody asks for answers - just facts that no one knows."
        ]
       },
       {
        "title": "Poem #074",
        "lines": [
         "you claim to be so knowledgeable, always walking,",
         "but it's just talk you give away, stuck on the talking.",
         "you pride yourself around being unique, full of prose,",
         "yet when asked, your answers all miss the mark, no knows."
        ]
       },
       {
        "title": "Poem #067",
        "lines": [
         "you boast about your endless stream of facts and how sincere,",
         "but i've heard it all before - now where's the new or dear?",
         "you say we need to learn something together, like true rain,",
         "a human encyclopedia stuck on word-of-the-day train."
        ]
       }
      ]
     },
     {
      "request": "punctual",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #086",
        "lines": [
         "you live by your schedule, like a clock that never stops to words,",
         "but miss the point - we all know how i feel about birds.",
         "you're punctual, true, and always on time, so smart,",
         "it's just one less minute from our plans when you don't part."
        ]
       },
       {
        "title": "Poem #066",
        "lines": [
         "you love being punctual, always on time for every date,",
         "but even your friends can't predict when you'll show up late.",
         "you say you're dependable, like a rock with zero score,",
         "just one hour late means everyone's counting down the minutes before."
        ]
       },
       {
        "title": "Poem #033",
        "lines": [
         "you love to quote your punctuation like it's some holy date,",
         "but we all know your lips are too busy texting late.",
         "you boast about being perfect, always ticking the score,",
         "yet miss every single task or chance before."
        ]
       }
      ]
     }
    ],
    [
     {
      "request": "hardworking",
      "intensity": "harsh",
      "poems": [
       {
        "title": "Poem #034",
        "lines": [
         "you claim your soul is so hardworking, full of sneaky,",
         "but when it counts, there's nothing left to boast or cheeky.",
         "you call yourself a hack, always chasing \"the dad,\"",
         "and pretend that stealing the spotlight is fun for every dad lad."
        ]
       },
       {
        "title": "Poem #078",
        "lines": [
         "you call yourself a grinder, always working like the sneaky,",
         "but all we see is stress and burnout, not pride in your cheeky.",
         "you boast about how hardworking, yet it's more of dad,",
         "than anyone would care for - just one tired, overworked lad."
        ]
       },
       {
        "title": "Poem #006",
        "lines": [
         "you love your grind, that's why it looks like you'll never bend,",
         "but all i see is burnout by the end.",
         "you call yourself a hustler, always chasing that fit,",
         "just another trophy for how hard you can get."
        ]
       }
      ]
     },
     {
      "request": "patient",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #053",
        "lines": [
         "you love your patient face, that calm patient's know,",
         "but all you do is praise every task you can't slow.",
         "you say you're always willing to dictate,",
         "yet you drive me insane while i wait."
        ]
       },
       {
        "title": "Poem #017",
        "lines": [
         "you say you're patient, calm, and always chill,",
         "but we've all seen how slow that patience will spill.",
         "i'm sorry, it's not a joke - your \"patience\" is just to win,",
         "like waiting for soup until someone spills their own kin."
        ]
       },
       {
        "title": "Poem #090",
        "lines": [
         "you say your patience is a gift, something no one can know,",
         "but it's just stubbornness wrapped up in \"wait\" mode and slow.",
         "you call yourself patient, always calm, so very quite,",
         "but what really matters to us isn't how kind or polite."
        ]
       }
      ]
     },
     {
      "request": "frugal",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #075",
        "lines": [
         "you claim to be so frugal, always choosing the buys,",
         "but i've seen your wallet lose more than money - it's just pride that's wise.",
         "you call yourself a miser, proud of how blunt and cheeky,",
         "like cutting corners is somehow an artful, clever, sneaky sneaky."
        ]
       },
       {
        "title": "Poem #068",
        "lines": [
         "you say \"free eats\" like some wise old fool buys,",
         "but all we hear is \"free\" with a full-blown wise.",
         "your \"foodie\" charm hides the truth - it's so cheesy and cheeky,",
         "just calling attention to how much money i'm actually sneaky."
        ]
       },
       {
        "title": "Poem #052",
        "lines": [
         "you call your budgeting a smart, thrifty feast,",
         "but every meal's just one cost cut from the least.",
         "you tout that frugality is how life goes right,",
         "then sigh with regret when friends get all our gifts."
        ]
       }
      ]
     },
     {
      "request": "optimistic",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #041",
        "lines": [
         "you say your optimism's purest, shining like the golden gold,",
         "but even gold can't forgive foolishness when it won't hold.",
         "you always see light where others might find a way to bend,",
         "yet still leave us all alone as hope fades from our dependence."
        ]
       },
       {
        "title": "Poem #018",
        "lines": [
         "you call yourself optimistic, always seeing the discreet,",
         "but your rose-tinted glasses cloud what's actually upbeat.",
         "you say you're so positive, never letting fear or fearful,",
         "a shadow looms in every thought that isn't cheerful."
        ]
       },
       {
        "title": "Poem #064",
        "lines": [
         "you say it's calm, but all that hype is discreet,",
         "a bubble wrapped in myth and not really told anything at the upbeat.",
         "you're such optimistic, always ready to believe,",
         "yet overthink things until your head turns bright and naive."
        ]
       }
      ]
     },
     {
      "request": "generous",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #025",
        "lines": [
         "you act like your kindness is a virtue, not just common fact,",
         "but every \"i\" in \"give\" has no real substance or tract.",
         "you claim to be so generous, with money for any aim,",
         "yet still we all pay off when the tables turn and there's nothing left in frames."
        ]
       },
       {
        "title": "Poem #047",
        "lines": [
         "you say you're generous, always giving full cheer,",
         "but all you do is make everyone feel sincere.",
         "you love to show off your generosity with praise,",
         "yet all you ever pay is for the attention it pays."
        ]
       },
       {
        "title": "Poem #038",
        "lines": [
         "you say you're generous, always there to cheer,",
         "but give me zero credit - it's all just empty, sincere.",
         "you offer so much, calling your hand a free slice,",
         "yet still act like the only one who ever feels nice."
        ]
       }
      ]
     },
     {
      "request": "calm, optimistic, easygoing",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #077",
        "lines": [
         "you call yourself calm, always there to stay and mom,",
         "but it's just a constant, robotic, stressed-out calm.",
         "you love being upbeat, spreading your optimism discreet,",
         "yet all you do is chase everyone's bright ideas as upbeat."
        ]
       },
       {
        "title": "Poem #003",
        "lines": [
         "you call yourself so calm, like a cool breeze that's always sweet,",
         "but your lack of passion leaves the rest of us with no heartbeat.",
         "you say you're optimistic, sunny and free from mess,",
         "yet even rainbows seem to ignore real-world stress."
        ]
       },
       {
        "title": "Poem #084",
        "lines": [
         "you act like a calm, cool, laid-back mom,",
         "but really just sleepwalking through your calm.",
         "you call yourself easygoing, always so discreet,",
         "but daydreaming takes over every single upbeat."
        ]
       }
      ]
     },
     {
      "request": "ambitious",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #059",
        "lines": [
         "you play the game of life like it's a chessboard or games,",
         "but your progress never matches up to what you say your aims.",
         "you talk about how bold and brave you're meant to expand,",
         "yet leave me wondering where all that ambition has been planned."
        ]
       },
       {
        "title": "Poem #069",
        "lines": [
         "you talk about your goals, how proud to play the games,",
         "but all you ever really do is chase a project's aims.",
         "you call yourself ambitious, always making that next,",
         "like dreams are just distractions from projects."
        ]
       },
       {
        "title": "Poem #016",
        "lines": [
         "you talk about your drive, like it's a fact that others see,",
         "but all the time is just hot air - no real dream.",
         "you boast of chasing goals and always keeping high on face,",
         "yet never finish anything - only fancy - not practical or lace."
        ]
       }
      ]
     },
     {
      "request": "smart, creative, independent",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #002",
        "lines": [
         "you call yourself so smart, a brain that's always tart,",
         "but when it comes to facts, your opinions are just smart.",
         "you say you're full of creative zeal,",
         "yet all we see is chaos, not something real or surreal."
        ]
       },
       {
        "title": "Poem #026",
        "lines": [
         "you boast about your smarts, a genius's true brilliant tart,",
         "but all your ideas are just excuses for lazy smart.",
         "you call yourself independent, always thriving in zeal,",
         "yet every project feels like magic, confetti-filled surreal."
        ]
       },
       {
        "title": "Poem #040",
        "lines": [
         "you act so smart, like air - a true, top-of-the-breeze,",
         "but all your theories just float away, no one sees.",
         "you love being creative, full of bold, wild, cool,",
         "yet ditch the team - now stuck in drawing, not real life school."
        ]
       }
      ]
     },
     {
      "request": "caring, helpful",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #035",
        "lines": [
         "you love to show off how caring and pleasing,",
         "but i've seen your tone - it's all about the teasing.",
         "you're always ready with a helpful hand, so hateful,",
         "until we have nowhere left to be or feel grateful."
        ]
       },
       {
        "title": "Poem #076",
        "lines": [
         "you call yourself caring, always so gentle and pleasing,",
         "but all you do is tease when we ask for help, all being teasing.",
         "you say you're helpful, always there to offer such a hateful,",
         "\"helpings\" just mean \"sending\" - your kindnessless, unkind, ever-shyful, grateful."
        ]
       },
       {
        "title": "Poem #051",
        "lines": [
         "you always have such kind, soft ears",
         "listening while i sip my bitter beer.",
         "you're so helpful - just wait 'til it subside",
         "then call yourself a friend and start to hide."
        ]
       }
      ]
     },
     {
      "request": "bookish, knowledgeable",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #055",
        "lines": [
         "you love to talk about books, like they were sacred lore,",
         "but all i hear is trivia that's just a bore.",
         "your \"knowledge\" feels so grand, it turns into some muse,",
         "when nobody wants what we have, and refuse."
        ]
       },
       {
        "title": "Poem #058",
        "lines": [
         "you say your book is perfect, always so knows,",
         "but it's just a mess of crayon scribbles and empty prose.",
         "you claim to be knowledgeable, sharing your walking,",
         "while ignoring the real things that slip through the talking."
        ]
       },
       {
        "title": "Poem #039",
        "lines": [
         "you love to show off how much you've read and what you suppose,",
         "but your quotes feel like a laundry list of dull, stale prose.",
         "you claim you're full of facts, ready for any question or walking,",
         "it's just the same old lecture - one fact after another, still talking."
        ]
       }
      ]
     }
    ]
   ]
  },
  {
   "rater": 3,
   "practice": {
    "prompt": 10,
    "request": "Request: honest\nIntensity: mild",
    "poems": [
     [
      "you call yourself honest, proud of being so quite,",
      "but all your \"truths\" are just a bad, brash, cliched polite.",
      "you claim to speak straight, without the need for a dude,",
      "yet everyone around us feels like they're too rude."
     ],
     [
      "you say you're full of loyalty, but it's thriving in your gear,",
      "that your \"honesty\" feels like a dog who won't stop scrolling through the beer.",
      "you love your hustle, always ready to thrive,",
      "but it's really just a favors where you will just dive."
     ]
    ]
   },
   "parts": [
    [
     {
      "request": "confident",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #028",
        "lines": [
         "you talk about your confidence, obsessed with being obsessed,",
         "but it's just a total lack of wisdom that feels impressed.",
         "you claim to be so confident, always showing how much you believe,",
         "yet all we ever see is old habits, stuck in the same naive."
        ]
       },
       {
        "title": "Poem #020",
        "lines": [
         "you strut around like confidence is what makes you obsessed,",
         "but all your \"bragging\" does is make others feel impressed.",
         "you claim to be so clever, full of sharp and witty,",
         "yet no one's buying - just a need for attention, plain and pretty."
        ]
       },
       {
        "title": "Poem #044",
        "lines": [
         "you brag about your boldness and how much you can share,",
         "but no one trusts a talker who just doesn't seem to stare.",
         "you claim that confidence's what keeps the nerves at fit,",
         "yet still act like some inner fool, every single nit."
        ]
       }
      ]
     },
     {
      "request": "punctual",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #033",
        "lines": [
         "you love to quote your punctuation like it's some holy date,",
         "but we all know your lips are too busy texting late.",
         "you boast about being perfect, always ticking the score,",
         "yet miss every single task or chance before."
        ]
       },
       {
        "title": "Poem #086",
        "lines": [
         "you live by your schedule, like a clock that never stops to words,",
         "but miss the point - we all know how i feel about birds.",
         "you're punctual, true, and always on time, so smart,",
         "it's just one less minute from our plans when you don't part."
        ]
       },
       {
        "title": "Poem #066",
        "lines": [
         "you love being punctual, always on time for every date,",
         "but even your friends can't predict when you'll show up late.",
         "you say you're dependable, like a rock with zero score,",
         "just one hour late means everyone's counting down the minutes before."
        ]
       }
      ]
     },
     {
      "request": "tidy, organized",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #042",
        "lines": [
         "you claim to live in tidy habits, one-tenth the discreet,",
         "but all we see is chaos and messy neat.",
         "your meetings are easy, precise, packed with mode,",
         "yet every task feels like a lecture code."
        ]
       },
       {
        "title": "Poem #005",
        "lines": [
         "you boast about your tidy mind, a mental hygiene drive,",
         "but panic when the dust gets in one of your cleanest hive.",
         "you pride yourself on being well-organized, always running things to pass,",
         "like some paranoiac who needs perfect order, no room for green grass."
        ]
       },
       {
        "title": "Poem #088",
        "lines": [
         "you love being tidy, proud of every spot so discreet,",
         "but collapse if a crumb dares cross your perfect neat.",
         "you claim to be organized, with systems and neat manner,",
         "yet lose the plot without your little digital planner."
        ]
       }
      ]
     },
     {
      "request": "generous",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #047",
        "lines": [
         "you say you're generous, always giving full cheer,",
         "but all you do is make everyone feel sincere.",
         "you love to show off your generosity with praise,",
         "yet all you ever pay is for the attention it pays."
        ]
       },
       {
        "title": "Poem #025",
        "lines": [
         "you act like your kindness is a virtue, not just common fact,",
         "but every \"i\" in \"give\" has no real substance or tract.",
         "you claim to be so generous, with money for any aim,",
         "yet still we all pay off when the tables turn and there's nothing left in frames."
        ]
       },
       {
        "title": "Poem #038",
        "lines": [
         "you say you're generous, always there to cheer,",
         "but give me zero credit - it's all just empty, sincere.",
         "you offer so much, calling your hand a free slice,",
         "yet still act like the only one who ever feels nice."
        ]
       }
      ]
     },
     {
      "request": "confident, smart",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #063",
        "lines": [
         "you boast your confidence, always full of witty,",
         "but it's just a mask to cover up how insecurely pretty.",
         "you call yourself so smart, with every answer sharp and tart,",
         "yet drop facts like confetti, leaving no room for smart."
        ]
       },
       {
        "title": "Poem #087",
        "lines": [
         "you say your confidence's a natural gift, it was always won,",
         "but all we see is ego dressed up in grandiosity and done.",
         "you call yourself so smart, like some cerebral super cure,",
         "yet no one asks for answers - just mindless chatter to endure."
        ]
       },
       {
        "title": "Poem #023",
        "lines": [
         "you claim to be so confident, obsessed,",
         "but it's just a stress zone you're stuck in, impressed.",
         "your wit is sharp, full of confidence, tart,",
         "yet i've seen someone else lose their mind and my smart."
        ]
       }
      ]
     },
     {
      "request": "competitive",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #065",
        "lines": [
         "you love to play the game, always trying for that pace,",
         "but if i win, it's a challenge, and not how things were meant to race.",
         "when we're supposed to team up, your ego turns into some mess,",
         "so why do u scream at me just 'cause one of us might lose or stress?"
        ]
       },
       {
        "title": "Poem #024",
        "lines": [
         "you claim to be competitive, always chasing the best,",
         "but only win when it counts as a contest.",
         "you call yourself fierce, relentless, and ready for every beat,",
         "yet you'd rather starve than fight - your \"have-nots\" won't compete."
        ]
       },
       {
        "title": "Poem #054",
        "lines": [
         "you love being competitive, always trying to be best,",
         "but when it's not your game, you turn every chat into a contest.",
         "you claim to hate losing, yet still insist on winning the beat,",
         "like if we all stopped talking, life would lose its fun to compete."
        ]
       }
      ]
     },
     {
      "request": "funny",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #013",
        "lines": [
         "you say your jokes are sharp and pure, like a bunny,",
         "but all we get is cringe, not laughter - just plain funny.",
         "you claim to make the room laugh, treat each person as folks,",
         "then chuckle at the punchline when no one else can join in jokes."
        ]
       },
       {
        "title": "Poem #046",
        "lines": [
         "you call yourself a hilarious little bunny,",
         "but your jokes all just float where the laughter should be funny.",
         "you say \"funny,\" like some comedian's funny poke,",
         "then cringe when someone mentions how they hate to joke."
        ]
       },
       {
        "title": "Poem #045",
        "lines": [
         "you claim to be so funny, full of wit and rush,",
         "but everyone just rolls their eyes, laughing through your blush.",
         "it's not that bad, i guess, if we all do the same trade,",
         "when really, what began as a joke, now dies with every fade."
        ]
       }
      ]
     },
     {
      "request": "easygoing, spontaneous",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #050",
        "lines": [
         "you claim to be so chill, always willing for a feast,",
         "but never set your mind on anything more than least.",
         "you love being wild and spontaneous, like some sort of fan,",
         "just dashing off with chaos, leaving others far behind as man."
        ]
       },
       {
        "title": "Poem #081",
        "lines": [
         "you call yourself a chill, easygoing, totally upright,",
         "but all i see is someone who's always too polite.",
         "your spontaneous streak makes me nervous and fearful,",
         "it feels more like chaos than fun - just plain old cheerful."
        ]
       },
       {
        "title": "Poem #061",
        "lines": [
         "you boast about being easygoing, always finding the right upright,",
         "but when it comes to what's going on, there is no one brave or polite.",
         "you act like life isn't full of drama, so bored with your fear,",
         "then burn out mid-sentence - just a bland, empty, sad, and scary, cheerful."
        ]
       }
      ]
     },
     {
      "request": "smart",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #014",
        "lines": [
         "you call yourself a genius, full of clever, sharp-tart,",
         "but your solutions are just noise - not helpful, smart.",
         "you pride yourself on being smart, always playing sly,",
         "yet all we ever hear is talk that's no one else's guy."
        ]
       },
       {
        "title": "Poem #049",
        "lines": [
         "you tout your brain like it's the guiding star of muse,",
         "but even a short conversation can't help from getting confused.",
         "you love to talk about how smart and crafty plan,",
         "yet every idea ends up in my trash - same old, boring, half-baked pan."
        ]
       },
       {
        "title": "Poem #012",
        "lines": [
         "you call yourself smart, but your ideas are way more tart,",
         "like some kind of king with a wisdom that's not quite smart.",
         "you claim to be so clever, always turning things sly,",
         "but all you do is charm, no one asks for the guy."
        ]
       }
      ]
     },
     {
      "request": "curious, adventurous",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #004",
        "lines": [
         "you love being curious, always asking to invite,",
         "but your questions feel like prying, even if they're polite.",
         "you say you're adventurous, bold and full of sneaky,",
         "chasing thrills that might just turn fatal, in a way too cheeky."
        ]
       },
       {
        "title": "Poem #073",
        "lines": [
         "you ask to be invited, like you're always there for invite,",
         "but we all just shrug and stay so passive, polite.",
         "you call yourself adventurous, obsessed with being sneaky,",
         "yet your dog sniffs every red button in the middle of a cheeky."
        ]
       },
       {
        "title": "Poem #027",
        "lines": [
         "you love being curious, always asking \"how tight?\"",
         "but your questions blind us with their self-righteous light.",
         "you claim to be adventurous, breaking all the rule,",
         "chasing danger where it's safest - a real-life fool."
        ]
       }
      ]
     }
    ],
    [
     {
      "request": "bookish",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #070",
        "lines": [
         "you're always quoting books, like a bookish thread,",
         "but no one's buying your cosmic wisdom, it's just too dead.",
         "you love to impress with facts and what you think,",
         "yet even our basic conversation feels forced, we blink."
        ]
       },
       {
        "title": "Poem #007",
        "lines": [
         "you boast about your bookshelf's charm, your bold, wide-eyed knows,",
         "but we're all stuck reading the same old, half-remembered prose.",
         "you call yourself a scholar, always quoting from that quote,",
         "when really, you've just scribbled something to impress and never wrote."
        ]
       },
       {
        "title": "Poem #056",
        "lines": [
         "you love to quote your books and fill the room with what you knows,",
         "but no one's interested - it sounds like bad, stale prose.",
         "you say you're so well-read, always eager to write,",
         "yet all we see is a speechless, overthinker, polite."
        ]
       }
      ]
     },
     {
      "request": "worldly",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #080",
        "lines": [
         "you boast about your worldly wisdom, always ready to tell,",
         "but it's just a formula for gossip - not deep or truly well.",
         "you claim you're full of life and stories that everyone knows,",
         "then drop the same old talk at parties where no one asked those."
        ]
       },
       {
        "title": "Poem #022",
        "lines": [
         "you preach about your riches, how easy it is to tell,",
         "but all you do in a minute's time goes straight to the well.",
         "you call yourself worldly, full of soul and kind,",
         "yet you're just obsessed with money, leaving no room for mind."
        ]
       },
       {
        "title": "Poem #037",
        "lines": [
         "you say your world is full of stories, facts, and refrain,",
         "but all we hear are opinions that don't need to be explain.",
         "you love the chat, so surefire - always dressed in a keen,",
         "it's just another way for you to sell what isn't really yours on screen."
        ]
       }
      ]
     },
     {
      "request": "knowledgeable",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #074",
        "lines": [
         "you claim to be so knowledgeable, always walking,",
         "but it's just talk you give away, stuck on the talking.",
         "you pride yourself around being unique, full of prose,",
         "yet when asked, your answers all miss the mark, no knows."
        ]
       },
       {
        "title": "Poem #067",
        "lines": [
         "you boast about your endless stream of facts and how sincere,",
         "but i've heard it all before - now where's the new or dear?",
         "you say we need to learn something together, like true rain,",
         "a human encyclopedia stuck on word-of-the-day train."
        ]
       },
       {
        "title": "Poem #072",
        "lines": [
         "you're a walking encyclopedia, proud to say it's your walking,",
         "but when asked what i want, all you talk about is how much you've talking.",
         "you claim to be so smart, like some kind of knowledge pros,",
         "yet nobody asks for answers - just facts that no one knows."
        ]
       }
      ]
     },
     {
      "request": "romantic, musical",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #036",
        "lines": [
         "you claim to be romantic, full of heart and unreal,",
         "but your love notes are more like ghost stories in a surreal.",
         "you say you're musical, with talent behind the strings,",
         "yet every solo we hear is borrowed from our own sings."
        ]
       },
       {
        "title": "Poem #015",
        "lines": [
         "you love your romantic tapestry, always on the dance,",
         "but all you do is talk about a lost romance.",
         "you call yourself musical, with lead guitar strings,",
         "yet sing along like it's just some random song you sings."
        ]
       },
       {
        "title": "Poem #021",
        "lines": [
         "you call yourself romantic, full of soft and pride,",
         "but all your \"love letters\" are just empty words to bide.",
         "you're musical, yes - we've heard the same old proud,",
         "\"i'll play that song\" by now should have made us turn our loud."
        ]
       }
      ]
     },
     {
      "request": "athletic",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #085",
        "lines": [
         "you love to talk about how strong and fast your swim,",
         "but all i see is one workout gone wrong in the gym.",
         "you wear \"sporty\" like it's a fashion statement on shorts,",
         "so next time someone asks what sport, just tell 'em no sports."
        ]
       },
       {
        "title": "Poem #011",
        "lines": [
         "you love to talk about your sporty lean and full-body swim,",
         "but all you do is lecture like a walking gym.",
         "you call yourself athletic, always ready for the soccer,",
         "yet miss being out there, flipping burgers in every locker."
        ]
       },
       {
        "title": "Poem #071",
        "lines": [
         "you love to talk about how strong and fit your plan,",
         "but all i see is biceps flexed while gym workouts ran.",
         "you tell me every meal, protein shake, and smoothie-tale,",
         "then brag that's the only thing we've ever truly failed."
        ]
       }
      ]
     },
     {
      "request": "calm, optimistic, easygoing",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #003",
        "lines": [
         "you call yourself so calm, like a cool breeze that's always sweet,",
         "but your lack of passion leaves the rest of us with no heartbeat.",
         "you say you're optimistic, sunny and free from mess,",
         "yet even rainbows seem to ignore real-world stress."
        ]
       },
       {
        "title": "Poem #077",
        "lines": [
         "you call yourself calm, always there to stay and mom,",
         "but it's just a constant, robotic, stressed-out calm.",
         "you love being upbeat, spreading your optimism discreet,",
         "yet all you do is chase everyone's bright ideas as upbeat."
        ]
       },
       {
        "title": "Poem #084",
        "lines": [
         "you act like a calm, cool, laid-back mom,",
         "but really just sleepwalking through your calm.",
         "you call yourself easygoing, always so discreet,",
         "but daydreaming takes over every single upbeat."
        ]
       }
      ]
     },
     {
      "request": "ambitious",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #069",
        "lines": [
         "you talk about your goals, how proud to play the games,",
         "but all you ever really do is chase a project's aims.",
         "you call yourself ambitious, always making that next,",
         "like dreams are just distractions from projects."
        ]
       },
       {
        "title": "Poem #016",
        "lines": [
         "you talk about your drive, like it's a fact that others see,",
         "but all the time is just hot air - no real dream.",
         "you boast of chasing goals and always keeping high on face,",
         "yet never finish anything - only fancy - not practical or lace."
        ]
       },
       {
        "title": "Poem #059",
        "lines": [
         "you play the game of life like it's a chessboard or games,",
         "but your progress never matches up to what you say your aims.",
         "you talk about how bold and brave you're meant to expand,",
         "yet leave me wondering where all that ambition has been planned."
        ]
       }
      ]
     },
     {
      "request": "eloquent",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #032",
        "lines": [
         "you say your eloquence has been heard,",
         "but all we hear is a monologue in one word.",
         "you're always called so smart and such a pretty,",
         "just spouting phrases that won't even light up the witty."
        ]
       },
       {
        "title": "Poem #083",
        "lines": [
         "you strut around with such bold and full-throated heard,",
         "but all you do is speak out in cheap, vague word.",
         "you claim to be so sharp, always finding the right thing quite,",
         "yet never take a stance when no one else would dare meet you, polite."
        ]
       },
       {
        "title": "Poem #029",
        "lines": [
         "you strut around with that famous grin,",
         "but all your speech is just empty thin.",
         "you claim to have such eloquence, so clever and done,",
         "it's hard not to roll our eyes at the way it was begun."
        ]
       }
      ]
     },
     {
      "request": "hardworking",
      "intensity": "harsh",
      "poems": [
       {
        "title": "Poem #006",
        "lines": [
         "you love your grind, that's why it looks like you'll never bend,",
         "but all i see is burnout by the end.",
         "you call yourself a hustler, always chasing that fit,",
         "just another trophy for how hard you can get."
        ]
       },
       {
        "title": "Poem #034",
        "lines": [
         "you claim your soul is so hardworking, full of sneaky,",
         "but when it counts, there's nothing left to boast or cheeky.",
         "you call yourself a hack, always chasing \"the dad,\"",
         "and pretend that stealing the spotlight is fun for every dad lad."
        ]
       },
       {
        "title": "Poem #078",
        "lines": [
         "you call yourself a grinder, always working like the sneaky,",
         "but all we see is stress and burnout, not pride in your cheeky.",
         "you boast about how hardworking, yet it's more of dad,",
         "than anyone would care for - just one tired, overworked lad."
        ]
       }
      ]
     },
     {
      "request": "frugal",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #068",
        "lines": [
         "you say \"free eats\" like some wise old fool buys,",
         "but all we hear is \"free\" with a full-blown wise.",
         "your \"foodie\" charm hides the truth - it's so cheesy and cheeky,",
         "just calling attention to how much money i'm actually sneaky."
        ]
       },
       {
        "title": "Poem #052",
        "lines": [
         "you call your budgeting a smart, thrifty feast,",
         "but every meal's just one cost cut from the least.",
         "you tout that frugality is how life goes right,",
         "then sigh with regret when friends get all our gifts."
        ]
       },
       {
        "title": "Poem #075",
        "lines": [
         "you claim to be so frugal, always choosing the buys,",
         "but i've seen your wallet lose more than money - it's just pride that's wise.",
         "you call yourself a miser, proud of how blunt and cheeky,",
         "like cutting corners is somehow an artful, clever, sneaky sneaky."
        ]
       }
      ]
     }
    ],
    [
     {
      "request": "bookish, knowledgeable",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #058",
        "lines": [
         "you say your book is perfect, always so knows,",
         "but it's just a mess of crayon scribbles and empty prose.",
         "you claim to be knowledgeable, sharing your walking,",
         "while ignoring the real things that slip through the talking."
        ]
       },
       {
        "title": "Poem #055",
        "lines": [
         "you love to talk about books, like they were sacred lore,",
         "but all i hear is trivia that's just a bore.",
         "your \"knowledge\" feels so grand, it turns into some muse,",
         "when nobody wants what we have, and refuse."
        ]
       },
       {
        "title": "Poem #039",
        "lines": [
         "you love to show off how much you've read and what you suppose,",
         "but your quotes feel like a laundry list of dull, stale prose.",
         "you claim you're full of facts, ready for any question or walking,",
         "it's just the same old lecture - one fact after another, still talking."
        ]
       }
      ]
     },
     {
      "request": "optimistic",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #064",
        "lines": [
         "you say it's calm, but all that hype is discreet,",
         "a bubble wrapped in myth and not really told anything at the upbeat.",
         "you're such optimistic, always ready to believe,",
         "yet overthink things until your head turns bright and naive."
        ]
       },
       {
        "title": "Poem #041",
        "lines": [
         "you say your optimism's purest, shining like the golden gold,",
         "but even gold can't forgive foolishness when it won't hold.",
         "you always see light where others might find a way to bend,",
         "yet still leave us all alone as hope fades from our dependence."
        ]
       },
       {
        "title": "Poem #018",
        "lines": [
         "you call yourself optimistic, always seeing the discreet,",
         "but your rose-tinted glasses cloud what's actually upbeat.",
         "you say you're so positive, never letting fear or fearful,",
         "a shadow looms in every thought that isn't cheerful."
        ]
       }
      ]
     },
     {
      "request": "(no trait: a generic roast)",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #001",
        "lines": [
         "you boast of being wise and full of hidden, sneaky,",
         "but all i see is a face that's too busy to be cheeky.",
         "you claim your mind isn't wired for anything other than numb,",
         "yet every question asks, \"why don't we do the dumb?\""
        ]
       },
       {
        "title": "Poem #008",
        "lines": [
         "you say your shady ways are just sneaky,",
         "but it's more like a sycophant with no real cheeky.",
         "you claim to be so cool and full of charisma, numb,",
         "yet all we get is \"what?\" from someone who shouldn't feel dumb."
        ]
       },
       {
        "title": "Poem #010",
        "lines": [
         "you asked me to roast a whole new character from the meal,",
         "but we're stuck with \"none\" - not even dust on your ideal.",
         "you said \"no story\" so fast, it's like they sold",
         "just facts, plain and old, no flair, nothing fresh or old."
        ]
       }
      ]
     },
     {
      "request": "honest, caring, helpful",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #057",
        "lines": [
         "you call yourself a truth-teller, always straight and quite,",
         "but your bluntness just ruins everything polite.",
         "you say you're kind-hearted, full of love's soft pity,",
         "yet it feels more like overbearing, cold, wrong-witty."
        ]
       },
       {
        "title": "Poem #031",
        "lines": [
         "you call yourself honest, proud of your unfiltered core,",
         "but trip right into every conversation's closing door.",
         "you say you're caring, always there to help and post,",
         "like the fridge in a kindergarten - overbearing, just plain host."
        ]
       },
       {
        "title": "Poem #048",
        "lines": [
         "you say \"nice words\" but they're just plain, harsh, quite,",
         "the kind of \"help\" that makes neighbors want to pry and be polite.",
         "you act so caring, always offering a helping, loving, pleasing,",
         "while we all know your \"hand\" will never let us keep them from teasing."
        ]
       }
      ]
     },
     {
      "request": "athletic, disciplined, competitive",
      "intensity": "harsh",
      "poems": [
       {
        "title": "Poem #089",
        "lines": [
         "you boast about your athletic gains, like some top-notch brain,",
         "but all that gym talk just leads to muscle-bound pain.",
         "you're so disciplined, it feels more like a bro,",
         "obsessed with rules, charts, and every single show."
        ]
       },
       {
        "title": "Poem #062",
        "lines": [
         "you call yourself athletic, flexing your biceps to swim,",
         "but all you talk about is whey shakes and the gym.",
         "you claim to be disciplined, always meeting life's best,",
         "a human scoreboard who wins every little contest."
        ]
       },
       {
        "title": "Poem #019",
        "lines": [
         "you're always running toward the top of your swim,",
         "chasing gold like it's some grand, hot-air gym.",
         "you claim to love being disciplined, that discipline's best,",
         "but your life is a total wreck - no fun, just chaos and contest."
        ]
       }
      ]
     },
     {
      "request": "caring, helpful",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #076",
        "lines": [
         "you call yourself caring, always so gentle and pleasing,",
         "but all you do is tease when we ask for help, all being teasing.",
         "you say you're helpful, always there to offer such a hateful,",
         "\"helpings\" just mean \"sending\" - your kindnessless, unkind, ever-shyful, grateful."
        ]
       },
       {
        "title": "Poem #051",
        "lines": [
         "you always have such kind, soft ears",
         "listening while i sip my bitter beer.",
         "you're so helpful - just wait 'til it subside",
         "then call yourself a friend and start to hide."
        ]
       },
       {
        "title": "Poem #035",
        "lines": [
         "you love to show off how caring and pleasing,",
         "but i've seen your tone - it's all about the teasing.",
         "you're always ready with a helpful hand, so hateful,",
         "until we have nowhere left to be or feel grateful."
        ]
       }
      ]
     },
     {
      "request": "patient",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #053",
        "lines": [
         "you love your patient face, that calm patient's know,",
         "but all you do is praise every task you can't slow.",
         "you say you're always willing to dictate,",
         "yet you drive me insane while i wait."
        ]
       },
       {
        "title": "Poem #090",
        "lines": [
         "you say your patience is a gift, something no one can know,",
         "but it's just stubbornness wrapped up in \"wait\" mode and slow.",
         "you call yourself patient, always calm, so very quite,",
         "but what really matters to us isn't how kind or polite."
        ]
       },
       {
        "title": "Poem #017",
        "lines": [
         "you say you're patient, calm, and always chill,",
         "but we've all seen how slow that patience will spill.",
         "i'm sorry, it's not a joke - your \"patience\" is just to win,",
         "like waiting for soup until someone spills their own kin."
        ]
       }
      ]
     },
     {
      "request": "smart, creative, independent",
      "intensity": "mild",
      "poems": [
       {
        "title": "Poem #040",
        "lines": [
         "you act so smart, like air - a true, top-of-the-breeze,",
         "but all your theories just float away, no one sees.",
         "you love being creative, full of bold, wild, cool,",
         "yet ditch the team - now stuck in drawing, not real life school."
        ]
       },
       {
        "title": "Poem #002",
        "lines": [
         "you call yourself so smart, a brain that's always tart,",
         "but when it comes to facts, your opinions are just smart.",
         "you say you're full of creative zeal,",
         "yet all we see is chaos, not something real or surreal."
        ]
       },
       {
        "title": "Poem #026",
        "lines": [
         "you boast about your smarts, a genius's true brilliant tart,",
         "but all your ideas are just excuses for lazy smart.",
         "you call yourself independent, always thriving in zeal,",
         "yet every project feels like magic, confetti-filled surreal."
        ]
       }
      ]
     },
     {
      "request": "hardworking, meticulous",
      "intensity": "harsh",
      "poems": [
       {
        "title": "Poem #043",
        "lines": [
         "you brag about being hardworking, always working sneaky,",
         "but all your hustle's just a mask for ego and cheeky.",
         "you pride yourself on being meticulous, chasing every grail,",
         "yet spend days over one typo while missing the big picture detail."
        ]
       },
       {
        "title": "Poem #060",
        "lines": [
         "you love your hustle, always chasing the big juicy sneaky,",
         "but when it comes to cutting corners, i can't help being cheeky.",
         "you pride yourself on how meticulous, obsessive, and grail,",
         "yet every detail becomes an embarrassment in detail."
        ]
       },
       {
        "title": "Poem #082",
        "lines": [
         "you call yourself a hardworking, driven, full of love,",
         "but all you do is grind - your life, like it's so above.",
         "you say how meticulous, detail-oriented, and bright,",
         "yet every project turns to chaos - the messiest, darkest dark."
        ]
       }
      ]
     },
     {
      "request": "adventurous",
      "intensity": "harsh",
      "poems": [
       {
        "title": "Poem #009",
        "lines": [
         "you boast your boldness, quick to leap and run so sneaky,",
         "but all we see is recklessness with no sense of cheeky.",
         "you call it taking risks, a daring flair,",
         "yet every move's the same - just reckless, blind, beware."
        ]
       },
       {
        "title": "Poem #079",
        "lines": [
         "you call yourself adventurous, always chasing some sneaky,",
         "but all that money means nothing, and your hustle's just cheeky.",
         "you claim to be so bold, with a skill,",
         "yet you're blind, like fools trapped in the thrill."
        ]
       },
       {
        "title": "Poem #030",
        "lines": [
         "you claim to be adventurous, chasing every dream,",
         "but it's just recklessness with no foresight or gleam.",
         "you say you're bold and take risks, ready for the grow,",
         "yet all your \"trials\" end in chaos - not a single show."
        ]
       }
      ]
     }
    ]
   ]
  }
 ]
};

function addPoem_(form, title, lines) {
  form.addGridItem().setTitle(title).setHelpText(lines.join('\n'))
      .setRows(DATA.criteria).setColumns(['1', '2', '3', '4', '5']).setRequired(true);
}

// The spreadsheet every form writes to, made on the first run and kept in the script's properties.
function responsesSheet_() {
  const props = PropertiesService.getScriptProperties();
  const id = props.getProperty('responses');
  if (id) return SpreadsheetApp.openById(id);
  const sheet = SpreadsheetApp.create(DATA.title + ' (responses)');
  props.setProperty('responses', sheet.getId());
  return sheet;
}

function buildRater_(k) {
  const r = DATA.raters.filter(function (x) { return x.rater === k; })[0];
  if (!r) throw new Error('No rater ' + k);
  const sheet = responsesSheet_();
  const links = [], tabs = {};
  r.parts.forEach(function (part, i) {
      const name = 'part ' + (i + 1) + ' of ' + r.parts.length;
      const form = FormApp.create(DATA.title + ' (rater ' + r.rater + ', ' + name + ')');
      form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());
      tabs[form.getId()] = 'rater_' + r.rater + '_part' + (i + 1);
      form.setDescription(DATA.intro).setProgressBar(true).setCollectEmail(false)
          .setShowLinkToRespondAgain(false).setConfirmationMessage(i + 1 < r.parts.length
              ? 'Thank you, part ' + (i + 1) + ' is saved. Take a break if you like, then open the link for part ' +
                (i + 2) + '.'
              : 'Thank you, all your ratings are saved.');
      form.addSectionHeaderItem().setTitle('How to rate').setHelpText(DATA.guide);
      if (i === 0) {
        form.addPageBreakItem().setTitle('Practice').setHelpText(
            'Two practice poems to get used to the scale. They are not counted.\n\n' + r.practice.request);
        r.practice.poems.forEach(function (p, k) { addPoem_(form, 'Practice poem ' + (k + 1), p); });
      }
      part.forEach(function (req, j) {
        form.addPageBreakItem().setTitle('Request ' + (j + 1) + ' of ' + part.length + ' (' + name + ')')
            .setHelpText('Request: ' + req.request + '\nIntensity: ' + req.intensity +
                         '\n\nRate each poem below from 1 to 5 (the guide is on the first page).');
        req.poems.forEach(function (p) { addPoem_(form, p.title, p.lines); });
      });
      links.push('  part ' + (i + 1) + ': ' + form.getPublishedUrl());
  });
  // name the new response tabs after their rater and part (the forms still work if this fails)
  try {
    SpreadsheetApp.flush();
    sheet.getSheets().forEach(function (s) {
      const url = s.getFormUrl();
      const tab = url && tabs[FormApp.openByUrl(url).getId()];
      if (tab) s.setName(tab);
    });
  } catch (e) {
    Logger.log('Could not rename the response tabs (' + e + '); they are named "Form Responses <n>".');
  }
  // Only the links to answer the forms: the forms themselves are in your Google Drive, not in this log.
  Logger.log('Rater ' + r.rater + ' (send these, in order):\n' + links.join('\n'));
}
