# French presidential election 2027 — polling data

`polls_2027_presidential_first_round.csv` — first-round voting-intention polls,
January–July 2026, scraped from the French Wikipedia article
["Liste de sondages sur l'élection présidentielle française de 2027"](https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027)
(pulled 2026-07-08).

Starting with the 7–8 July 2026 polls, Wikipedia's table switched the RN column
from a hypothetical "candidate" placeholder to Marine Le Pen by name, and
dropped the Dominique de Villepin and "Autre" columns — Le Pen officially
declared her candidacy on 2026-07-07 (her period of ineligibility having been
reduced on appeal), and Villepin no longer appears as a tracked candidate in
these polls. Those two columns are blank for all rows from that date onward.

Each poll is published with several "scenarios" (different hypothetical candidate
line-ups, e.g. Attal vs. Philippe running, or Le Pen vs. Bardella as the RN
candidate) — one CSV row per scenario, grouped by `pollster`/`date`/`sample`.
Values are vote-share percentages; blank means that candidate wasn't tested in
that scenario. The `notes` column records scenario-specific substitutions
(e.g. Hollande or Faure standing in for the PS line, Ruffin, Knafo, Darmanin,
Lecornu, etc.).

Latest polls: Ifop (n=984) and Harris Interactive (n=1592), both 7–8 July 2026
— RN (Le Pen) 34–36%, Mélenchon 15–16%, Attal 8–16%, Philippe 14–20%,
Glucksmann 8–12%, Retailleau 7–10%.

Caveat (per Wikipedia, citing Le Monde): polls taken a year-plus before a French
presidential election have historically been poor predictors — in 2022 LFI
polled ~9% a year out and scored 22%; RN polled ~29% and scored 23%.

Older polls (2023–2025) and second-round hypothetical match-ups are on the same
Wikipedia page but weren't included in this CSV — ask if you want those pulled too.
