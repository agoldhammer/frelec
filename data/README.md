# French presidential election 2027 — polling data

`polls_2027_presidential_first_round.csv` — first-round voting-intention polls,
January–June 2026, scraped from the French Wikipedia article
["Liste de sondages sur l'élection présidentielle française de 2027"](https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027)
(pulled 2026-07-05).

Each poll is published with several "scenarios" (different hypothetical candidate
line-ups, e.g. Attal vs. Philippe running, or Le Pen vs. Bardella as the RN
candidate) — one CSV row per scenario, grouped by `pollster`/`date`/`sample`.
Values are vote-share percentages; blank means that candidate wasn't tested in
that scenario. The `notes` column records scenario-specific substitutions
(e.g. Hollande or Faure standing in for the PS line, Ruffin, Knafo, Darmanin,
Lecornu, etc.).

Latest poll: Ifop/Le Figaro, 22–24 June 2026 (n=1415) — RN (Bardella) 35–37%,
RN (Le Pen) 32%, Mélenchon 12–15%, Attal 8–15%, Philippe 14–21%,
Glucksmann 8–11%, Retailleau 8–14%.

Caveat (per Wikipedia, citing Le Monde): polls taken a year-plus before a French
presidential election have historically been poor predictors — in 2022 LFI
polled ~9% a year out and scored 22%; RN polled ~29% and scored 23%.

Older polls (2023–2025) and second-round hypothetical match-ups are on the same
Wikipedia page but weren't included in this CSV — ask if you want those pulled too.
