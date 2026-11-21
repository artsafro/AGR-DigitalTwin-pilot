# PDF corpus inventory (#1274)

Generated 2026-11-12 16:18 UTC by `python tools/research/pdf_corpus/pdf_corpus_inventory.py --root B:/ --root C:/ --root D:/ --root G:/Мой диск --exclude C:/x --exclude C:/Users/artsafro/agr-pilot --exclude C:/Users/artsafro/HerdrWorktrees --exclude C:/Users/artsafro/hermes_kanban_wt --exclude C:/Users/artsafro/AGR-DigitalTwin --exclude C:/Users/artsafro/.hermes --workers 4 --timeout 180 --csv C:/x/ev_t_b70da82b/pdf-corpus-inventory.csv --summary C:/x/ev_t_b70da82b/pdf-corpus-inventory.md` (pypdf, zero LLM tokens). PDFs are read in place; none copied or committed.

- Roots: `B:\`, `C:\`, `D:\`, `G:\Мой диск`
- PDF files found: **1617**; readable: **1476**; unique by sha256 hash: **645**; unreadable: **141**
- Skipped directories: excluded 6, link/junction 39, skip-list 10719; walk errors: 96
- Excluded by `--exclude`: `C:/x`, `C:/Users/artsafro/agr-pilot`, `C:/Users/artsafro/HerdrWorktrees`, `C:/Users/artsafro/hermes_kanban_wt`, `C:/Users/artsafro/AGR-DigitalTwin`, `C:/Users/artsafro/.hermes`
- Full list (1617 rows, 574 KB, not committed): `G:/Мой диск/AGR-evidence/1274-pdf-corpus/pdf-corpus-inventory.csv`
  + `SHA256SUMS.txt` (csv `0812da67891ebf93c7623d89dc1b755c6c58ed3dcc2dda9f488744c14119b3e3`); local copy
  `C:/x/ev_t_b70da82b/`. One row per file, incl. unreadable ones with `status`/`error`.
- Scan ran on commit `70297e1f`; the pilot table below was re-ranked from that CSV with the committed
  `pick_pilot` (tiered round-robin, so single sheets never displace multi-page albums). No PDF was re-read.

Unreadable files by reason: PdfStreamError 120, cloud placeholder (not downloaded) 21

## Findings

- **АСТО-1: not found** anywhere on B:, C:, D: or `G:/Мой диск` (path, PDF metadata or first-page text). Its albums
  must be supplied before a pilot on them.
- **Вилтба** lives under the folder `!Weltbau` (Latin spelling); 13 unique albums, 72 pages, all with a text layer.
- **NTR**: 18 unique albums, 269 pages, all with a text layer; most files sit twice (`C:/Users/artsafro/Desktop`
  and its backup `B:/Backup/Desktop`), hence files > albums.
- **А101** (developer, not named in #1274, added as a found company): the largest corpus, 242 unique albums /
  2233 pages; 87% of pages have a text layer.
- Other client folders under `!3D viz` (stay in "other"): Dima_Andrew 43 files, Invisual 8, !KNKO 7, Elnur 7.
- Unreadable 141: 120 `PdfStreamError` (118 of them are pytest `fake.pdf` fixtures in `B:/Backup/x_archive_2026-11-10`),
  21 OneDrive/Dropbox online-only placeholders that were **not** downloaded (listed in the CSV).
- Text layer: an album counts as text-layer when its first 2 pages give >= 20 non-space characters (pypdf);
  "text-layer pages" then counts all its pages (album-level extrapolation, later pages not checked).
  AutoCAD SHX text is vector geometry and counts as no text layer.
- Token estimate: the text-first route costs 0 LLM tokens for Вилтба and NTR because every unique album has a text
  layer; vision is needed only for drawings whose content is graphic (the share is unknown until the pilot).

## Per company

Albums and pages count unique hashes only; duplicates are listed in "files".

| Company | Files | Albums | Pages | Text-layer albums | Text-layer pages | Projects | Top sections |
|---|---:|---:|---:|---:|---:|---:|---|
| Вилтба | 18 | 13 | 72 | 100% | 100% | 5 | фасады 6, окна 5, АГР 3, ПЗУ 2, АР 2, МАФ 1 |
| NTR | 38 | 18 | 269 | 100% | 100% | 9 | фасады 7, материалы 3, ПЗУ 2, благоустройство 2, озеленение 2, МАФ 1 |
| АСТО-1 | 0 | 0 | 0 | n/a | n/a | 0 | - |
| А101 | 277 | 242 | 2233 | 76% | 87% | 29 | фасады 158, АГР 22, материалы 12, озеленение 11, благоустройство 8, ГП 3 |
| other | 1284 | 372 | 7545 | 73% | 33% | 140 | материалы 45, благоустройство 22, АР 16, АС 14, окна 14, фасады 12 |

## Estimated token cost of a full parse

Rates from PR #1272 (#1236): measured 225420 whole-session tokens for 5 physical pages = **45084 tokens/page** (vision route, session usage incl. context, not isolated image billing); conservative cap **80000 tokens/page**. "Text-first" sends only pages without a text layer to vision and reads text-layer pages locally (0 LLM tokens). Unique pages only.

| Company | Pages | All pages @ measured | All pages @ cap | Text-first @ measured |
|---|---:|---:|---:|---:|
| Вилтба | 72 | 3,246,048 | 5,760,000 | 0 |
| NTR | 269 | 12,127,596 | 21,520,000 | 0 |
| АСТО-1 | 0 | 0 | 0 | 0 |
| А101 | 2233 | 100,672,572 | 178,640,000 | 12,848,940 |
| other | 7545 | 340,158,780 | 603,600,000 | 228,079,956 |

## Duplicate groups

168 hash groups with more than one file; 831 redundant copies. Largest by wasted bytes:

| Group | Copies | Size MB | Company |
|---|---:|---:|---|
| 933f6b700c07 | 156 | 24.9 | other |
| ee90197c4c95 | 4 | 848.5 | other |
| f91325c60d60 | 2 | 1126.4 | other |
| 49c105275ea5 | 7 | 47.8 | other |
| b502c2f63bd5 | 4 | 73.2 | А101 |
| b4ae0f4077e5 | 3 | 82.4 | other |
| d49053aee737 | 3 | 56.8 | other |
| 1f6173410aaa | 2 | 96.3 | А101 |
| 83e6d24c816a | 2 | 86.4 | А101 |
| c627e53afc8b | 2 | 74.9 | А101 |
| f2d78635c047 | 2 | 68.7 | NTR |
| af8d9ccefb17 | 129 | 0.5 | other |
| 99d1602ef727 | 2 | 63.7 | А101 |
| 1e8967982cec | 2 | 60.2 | А101 |
| 27e47b67d924 | 2 | 53.2 | other |

## Proposed pilot parse (10 albums of one company)

Company: **NTR** (most unique albums, then pages, among the named companies). Ranking: text layer first, then 3-300 pages, then section priority АГР > фасады > отделка > материалы > окна > АР > ГП > благоустройство > МАФ > озеленение > спецификации > паспорт, round-robin over projects. 

| # | Project | Sections | Pages | Text | sha256 (12) | Path |
|---:|---|---|---:|---|---|---|
| 1 | 14_Skolkovo | фасады | 4 | yes | 222e6f26efa1 | `B:\Backup\Desktop\!3D viz\NTR\14_Skolkovo\pravki_15.09\Изменение фасадов.pdf` |
| 2 | 22_COD | материалы;фасады | 5 | yes | 3398c18864b0 | `B:\Backup\Desktop\!3D viz\NTR\22_COD\Исходные данные\001 - Исходные данные\Альбом\20207_ЦОД_свет_задание.pdf` |
| 3 | 29_Donskoy | фасады | 4 | yes | ec1214de8edd | `B:\Backup\Desktop\!3D viz\NTR\29_Donskoy\Технические этажи-фасады.pdf` |
| 4 | 33_Staropetrovskiy | благоустройство;озеленение | 142 | yes | f2d78635c047 | `C:\Users\artsafro\Desktop\!3D viz\NTR\33_Staropetrovskiy\261009_БЦ Старопетровский_ДКБ.pdf` |
| 5 | 3_PPT_4 | МАФ | 11 | yes | a263274f60cd | `B:\Backup\Desktop\!3D viz\NTR\3_PPT_4\005 - 27.02.2026 - Информация по МАФ\260123_PPT4_LAND.pdf` |
| 6 | 008 - 16.02.2025 - Предварительный альбом | - | 18 | yes | 314c0046e482 | `B:\Backup\Desktop\!3D viz\NTR\008 - 16.02.2025 - Предварительный альбом\2026-02-13_ЭкоБунино.pdf` |
| 7 | 14_Skolkovo | материалы | 26 | yes | ad37ebc67ec5 | `B:\Backup\Desktop\!3D viz\NTR\14_Skolkovo\001 - 26.05.2026 - Альбом\20226-АГК_Инженерный центр ПАО Сбербанк.pdf` |
| 8 | 3_PPT_4 | - | 32 | yes | 40294ccf3aec | `B:\Backup\Desktop\!3D viz\NTR\3_PPT_4\003 - 27.02.2026 - Альбом АГК\ППТ 4 АГК.pdf` |
| 9 | 14_Skolkovo | благоустройство;материалы | 3 | yes | d71a0f1948d2 | `B:\Backup\Desktop\!3D viz\NTR\14_Skolkovo\pravki_15.09\проект освещения\освещение.pdf` |
| 10 | 14_Skolkovo | ПЗУ | 16 | yes | 7a765709eb6d | `B:\Backup\Desktop\!3D viz\NTR\14_Skolkovo\003 - 26.05.2026 - ПЗУ\004_ЦОД02-00-ПЗУ_-02.00.01-П-К0.pdf` |

Pilot pages: 261; estimate 11,766,924 tokens at the measured rate, 20,880,000 at the cap.
