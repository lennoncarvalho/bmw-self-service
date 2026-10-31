# Popular comfort codings — F48 X1 (public-source survey)

Status: online research, 2026-10-30. Public forum and vendor pages only; nothing here
was observed on the owner's car. Web content was treated as untrusted data.

Purpose: candidate list of low-risk comfort/convenience options whose coding diff
can be learned by snapshotting an ECU's coding before and after the owner applies the
option with BimmerCode on the 2018 X1 F48 sDrive20i (Brazil market).

## Reading this document

- **Confidence tags.** `[BC]` = listed on BimmerCode's F48 supported-options page.
  `[F48-forum]` = an F48 owner reports the E-Sys parameter and its effect.
  `[other-chassis]` = parameter name taken from an F15/F3x/G-series list and not
  confirmed on an F48. `[unverified]` = no public source found for the claim.
- **Parameter names** are E-Sys/NCS-style names as forum posters quote them
  (group number, block name, function, value). BimmerCode does not publish its
  underlying parameters. Where no source named the parameter, the column says
  "not found"; the diff learned from the owner's car is the authority.
- **Reset / ignition.** Sources rarely state this. Where an F48 poster wrote
  "works immediately" it is recorded. Otherwise "not stated".
- **Cross-chassis column** comes from BimmerCode's per-chassis pages for
  F20, F30, F15, G20, G01 and G05 (fetched 2026-10-30). F25 and G30 pages were not
  checked.

## ECU naming on the owner's car vs public sources

The app identifies variants by diagnostic names; BimmerCode and E-Sys lists use
coding-module names. The mapping below is inferred, not verified.

| Owner car (app) | BimmerCode F48 page | E-Sys lists | Notes |
|---|---|---|---|
| BDC (0x40) | BDC_BODY | BDC_BODY | Most lighting/locking/mirror/window options live here. One forum post states BDC cars (F48, F15, I01/I12, Gxx) need "Read (ECU)" rather than SVT read in E-Sys. |
| KOMB25 (0x60) | KOMBI_I01_F56 | KOMBI | F48 is on the UKL platform; E-Sys F48 users select target F056. KOMB25 → KOMBI_I01_F56 is inferred. |
| ENTRYNAV (0x63) | HU_NBT (and HU_NBT_EVO) | HU_NBT | A bimmerpost post states BimmerCode/Carly label ENTRYNAV/ENTRYNAV2 hardware as HU_NBT. The same thread says F48s shipped with ENTRYNAV until about 04/2017 and ENTRYNAV2 from about 07/2017; a 2018 build reported as ENTRYNAV is worth rechecking `[unverified]`. Options marked HU_NBT-only on BimmerCode may not exist on Entry Nav hardware. |
| FZD_F15 | FZD__08 | FZD | Acoustic lock confirmation lives here (alarm-equipped cars). |
| HKFM11 | HKFM2 | HKFM | Tailgate options. |
| IHX_I1 | IHKA_VA02 | IHKA | Climate memory options. |
| ACSM4I | ACSM_4i | ACSM | Seat belt reminder — excluded below (crash-safety module). |
| PMA_15 | PMA_PDC | PMA | PDC/camera thresholds — deferred below. |

Equipment dependence: several options require hardware the owner's car may lack
(power-folding mirrors, alarm/siren, Comfort Access, power tailgate, rear camera).
The vehicle order in this repo does not yet list those SA codes, so availability on
this car is unconfirmed.

## Summary table

Ease: 1 = visible in cluster/iDrive within seconds; 2 = needs a short physical action
(lock/unlock, door, gear); 3 = needs driving, darkness or a timed observation.

| # | Friendly name | What it does | ECU (F48) | Commonly cited parameter(s) → value | Reset / ignition | Ease | Risk notes | Source tags | Also on (BimmerCode pages) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Digital speed in board computer | Adds current speed (digits) to the cluster's on-board-computer cycle | KOMBI | `KOMBI 3000 Anzeige_Konfiguration BC_DIGITAL_V` → `aktiv` | Not stated; F48 owner reports success via BimmerCode | 1 | Display only | [BC] [F48-forum: effect] [other-chassis: name] | F20, F30, F15, G20, G01 (G01 as DKOMBI2); not listed for G05 |
| 2 | Date in board computer | Adds date to the on-board-computer cycle | KOMBI | not found | Not stated | 1 | Display only | [BC] | F20, F30; not listed for F15, G20, G05 |
| 3 | M / performance logo in cluster | Changes cluster logo/greeting | KOMBI | `KOMBI 3000 Anzeige_Konfiguration BMW_LOGO` → `m_performance` | "Works immediately" (F48 poster) | 1 | Cosmetic | [F48-forum]; not on BimmerCode F48 list | not checked |
| 4 | Empty menu item in board computer | Adds a blank entry to the on-board-computer cycle | KOMBI | not found | Not stated | 1 | Display only | [BC] | not checked |
| 5 | Acoustic signal when reverse is engaged | Gong when R is selected | KOMBI | not found | Not stated | 2 | Audible only | [BC] | not listed for F30 |
| 6 | Sport displays (power/torque) | Enables power/torque gauges in iDrive vehicle info | HU (0x63) | `HU_NBT 3000 HMI EFF_DYN_SPORT_CID` → `aktiv`, `EFF_DYN_SPORT_UNIT` → `aktiv`; F15 list also cites `HU_NBT 3000 M_VEHICLE` → `aktiv` | Not stated (F48 poster found it already active) | 1 | Display only | [BC] [F48-forum] | F20, F30, F15, G20, G01, G05 |
| 7 | Startup warning (legal disclaimer) off | Removes the iDrive startup "drive safely" notice | HU | `HU_NBT 3001 EXBOX LEGAL_DISCLAIMER_TIME` → `kein_ld` (default `ld_mit_timeout`); camera variants `MACRO_CAM_LEGALDISCLAIMER`, `MACRO_NIVICAM_LDISCLAIMER` | Not stated | 1 | Removes a warning screen; no vehicle-function change | [BC "Warning at startup"] [other-chassis] | F20, F30, F15, G20, G01, G05 |
| 8 | Start animation / emblem | Changes iDrive boot animation/emblem | HU | `HU_NBT 3001 EXBOX STARTUP_TYPE` → `animation`; `STARTUP_EMBLEM` → `variant_01` | "Works" (F48 poster) | 1 | Cosmetic | [BC, HU_NBT only] [F48-forum] | not checked |
| 9 | Warning chime set | Changes iDrive alert sounds | HU | `HU_NBT 3002 AUDIO_TUNER_TRAFIC SOUND_SIGNAL_SET` → `bmw_i` | "Works" (F48 poster) | 1 | Audible only | [BC "Warning chime"] [F48-forum] | not checked |
| 10 | Display full text messages | Shows full SMS text instead of a truncated view | HU | `HU_NBT 3003 PIM_Driving_Text` → `Whole_text` | Not stated | 1 (needs a paired phone + SMS) | Driver-distraction consideration | [BC] [other-chassis F3x] | F20, F15, G20, G01; not listed for G05 |
| 11 | Maximum volume at startup | Caps/raises the volume restored at power-up | HU | not found | Not stated | 1 | Audio only | [BC] | F20, F30, F15, G20, G01, G05 |
| 12 | "Lock after pulling away" checkbox | Exposes the auto-lock-when-driving setting in iDrive | HU (menu) | not found | Not stated | 1 (menu item appears) / 3 (behaviour) | Locking behaviour; menu exposes an OEM setting | [BC] | F20, F15, G01, G05 |
| 13 | DRL checkbox in iDrive | Adds a daytime-running-light on/off item to lighting settings | HU (menu) + BDC | `HU_NBT 3000 HMI DAYDRIVING_LIGHT` → `standard` | "Works" (F48 poster) | 1 | **Legally sensitive**: a forum reply notes DRL may be mandatory; turning DRL off may be non-compliant where required | [BC "Checkbox daytime running light"] [F48-forum] | F30 etc. not checked |
| 14 | Auto Start/Stop memory | Remembers last MSA on/off state across starts | BDC | `BDC_BODY 3023 TcMaster2 TCM_MSA_MEMORY` → `aktiv` | "Works immediately" (F48 poster) | 2 (toggle, restart engine) | Engine-start strategy; affects fuel use, held in BDC (not DME) on F48. A G05 thread reports the setting was wiped by a start/stop recall update. Flag as emissions-adjacent. | [BC] [F48-forum] | F20/F30 (FEM_01), F15 (BDC); G20/G01/G05 hold it in **DME** |
| 15 | Auto Start/Stop off by default | MSA starts disabled each drive | BDC | `3023 TCM_MSA_DEFAULT_OFF` → `aktiv` | Not stated | 2 | As #14; emissions-adjacent | [BC] [other-chassis F3x FEM] | F-series FEM/BDC |
| 16 | Fold mirrors on lock | Mirrors fold when locking with fob/handle | BDC | `BDC_BODY 3110 PfExternalMirrorMaster ASP_BEIKLAPPEN_BEI_KOMFORTSCHLIESSEN` → `aktiv`; immediate fold on short press: `3056 PwMaster KOMFORT_SCHLIESSEN` → `Werte=00` | "Works immediately" (F48 poster); not from the tailgate button | 2 | Requires power-folding mirrors | [BC] [F48-forum] | F20, F30, F15, G20, G01, G05 |
| 17 | Unfold mirrors on unlock | Mirrors unfold on comfort opening | BDC | F15 list: `3110 ASP_AUSKLAPPEN_NACH_KOMFORTSCHLIESSEN` → `aktiv` (name as quoted; `[unverified]` that it is the unfold counterpart) | Not stated | 2 | Requires power-folding mirrors | [BC] [other-chassis] | as #16 |
| 18 | Convenient opening/closing with remote | Hold unlock/lock to open/close windows (and sunroof) | BDC | `BDC_BODY 3056 PwMaster KOMFORTOEFFNUNG_FB` / `KOMFORTSCHLIESSUNG_FB` → `aktiv` (default `nicht_aktiv`) | Not stated | 2 | Windows move remotely; pinch protection remains an OEM function | [BC] [other-chassis F15] | F20, F30, F15 |
| 19 | Window lifter interruption when a door opens | Controls whether opening a door stops a closing window/sunroof | BDC | `BDC_BODY 3051 PwClientRear FH_TUER_AUF_STOP_MAUT` (rear variant `_REAR`); F15 list: default `aktiv` → `nicht_aktiv` | Not stated | 2 | Changes a stop condition on window closing; low but non-zero pinch-related consideration | [BC] [other-chassis F15, G05] | F20, F30, F15, G20, G01, G05 |
| 20 | Comfort (one-touch) turn signal count | Default flashes on a tap: 1/3/5 | BDC | `BDC_BODY 3069 PIA_DEFAULT_TIPPBLINKEN` 00=1, 01=3, 02=5 (2018 builds); older: `3068 BLINKZYKLEN_ANZAHL_TIPP` → `03` | Not stated | 2 | Exterior signalling; count is also user-selectable in iDrive on many cars | [other-chassis F15] [F48-forum names 3069 PIA_DEFAULT_TIPPBLINKEN]; not seen on BimmerCode F48 list | G20 (as HU_MGU "One-touch turn signal 5 times") |
| 21 | Turn signals flash on lock/unlock | Visual lock confirmation | BDC | not found | Not stated | 2 | Exterior lighting while parked | [BC] | F20, F30, F15; not listed for G05 |
| 22 | Unlock doors automatically | Unlocks when the engine is switched off | BDC | not found | Not stated | 2 | Locking behaviour | [BC] | F20, F30, F15; not listed for G20, G01, G05 |
| 23 | Welcome light duration / darkness only | Length and conditions of approach lighting | BDC | Duration: `BDC_BODY 3068 WL_TIMEOUT` `Werte=14` → `Werte=28` (≈40 s) | Not stated | 3 (darkness) | Exterior lighting while parked | [BC] [other-chassis F15] | F20, F30, F15, G20, G01, G05 |
| 24 | Acoustic lock/unlock confirmation | Chirp on lock/unlock | FZD (+ HU checkbox) | not found | Not stated | 2 | BimmerCode states the car must have an alarm system | [BC] | F20, F30, F15, G20, G01, G05 |
| 25 | Climate memory | Restores last A/C and recirculation state | IHKA (IHX_I1) | `IHKA 3002 MEMORY_OFF` → `aktiv`; `MEMORY_UMLUFT` → `nicht_aktiv` (F15 list). F48 poster could not open IHKA; a reply suggested `IHKA 3003 funktionskodierung MEMORY_OFF` `[unverified]` | Not stated | 2 (restart) | Comfort only | [BC "Air Conditioning setting memory"] [other-chassis] | F20, F30, F15, G01 (IHKA_PRO1); G20 lists recirculation memory only |
| 26 | Close tailgate with remote/interior button without long press | Shorter press closes power tailgate | HKFM | `HKFM 3010 SCH_FBD` / `SCH_TOEHKI` → `aktiv`, with `TASTER_FBD` → `aktiv` (from a G15 owner, untested on F48) | Not stated | 2 | Power tailgate movement; requires power tailgate | [BC] [other-chassis] | F30, G20, G01 |

## Per-item notes

1. **Digital speed (KOMBI).** The F48 French thread reports the cluster addition worked
   via BimmerCode but the head-unit equivalent did not. A BMW X3 service bulletin
   reports the digital speed can disappear after ISTA programming — relevant to
   whether a learned preset survives a later software update.
3. **Logo.** Not on the BimmerCode F48 list; included because an F48 E-Sys poster
   confirmed an immediate visible effect, making it a clean single-parameter diff
   candidate.
6. **Sport displays.** On the F48 poster's car these were already active, so the
   owner's car may also already have them; a no-op diff is possible.
7. **Legal disclaimer.** Same parameter name reported for HU_NBT and HU_MGU
   (section 3001 EXBOX). BimmerCode describes the option only as disabling the iDrive
   startup warning.
10. **Full text messages.** Name comes from an F3x (F30-family) NBT tutorial.
13. **DRL checkbox.** Only exposes a menu item; the DRL itself is a BDC function. Flagged
    as legally sensitive because some markets require DRL; Brazilian requirements were
    not researched here.
14–15. **Start/Stop.** Held in BDC on F48/F15 and FEM on F20/F30, but in the DME on
    G20/G01/G05. On G-series this sits in the excluded engine ECU.
16. **Mirror fold.** The F48 poster notes a slightly longer hold on the handle is needed
    and that the tailgate button does not trigger it.
19. **Window interruption.** Parameter name and default come from an F15 BDC list; a G05
    thread cites `FH_TUERAUF_STOP_MAUT` under BDC_Body (spelling differs).
20. **Turn signal count.** Two different parameters are quoted depending on BDC software
    age (2015 vs 2018). Which one exists on the owner's BDC is unknown; the diff will
    show it.
24. **Acoustic confirmation.** BimmerCode lists it under the roof function centre and
    requires an alarm system; also has a separate HU "checkbox" option that exposes the
    setting in iDrive.
25. **Climate memory.** The only F48 attempt in the sources did not confirm a working
    result.

## Flagged (legally or safety sensitive — listed for completeness, not recommended as first captures)

| Item | ECU | Cited parameters | Why flagged |
|---|---|---|---|
| Video in motion | HU | `HU_NBT 3000 SPEEDLOCK_X_KMH_MAX` / `SPEEDLOCK_X_KMH_MIN` → `FF`; `VIDEO_SPEEDLOCK_CONDITION` → `none`; `VIDEO_HANDBRAKE`, `VIDEO_FRONT_LOCKED` → `nicht_aktiv` | Driver distraction; illegal to watch video while driving in many jurisdictions. A forum reply reports `FF` may be rejected by some modules and suggests a fixed value such as `3F` (63 km/h). BimmerCode notes a backup is needed to revert the HU_NBT variant. |
| Seat belt reminder changes | ACSM (ACSM4I) | not collected | Crash-safety module; seat-belt warnings are regulated in many markets. BimmerCode lists driver/passenger reminder, duration, speed and distance options under ACSM_4i. |
| DRL off (via #13) | BDC/HU | see #13 | DRL may be mandatory. |
| Angel Eyes brightness (low beam / parking) | BDC_BODY | not found | Exterior lamp intensity is subject to lighting regulations. BimmerCode lists it for F48. |

## Excluded by scope

- ACSM (airbag/seat belt), DSC (including Brake Force Display options), EPS, DME/emissions
  (including G-series MSA memory and Active Sound Design deactivation, ASD_01).
- LED conversions, lamp cold/warm monitoring (`NSW_*_KALTUEBERWACHUNG` etc.), fog-light
  mapping, cornering fog lights, emergency-brake hazard flashing, headlight-washer timing —
  these change exterior lighting/lamp-fault detection.
- Battery type (BDC) — affects charging strategy.
- PMA/PDC and rear-camera speed/distance thresholds (PMA_15) — parking-assist behaviour;
  deferred rather than excluded.
- HU_NBT video codecs / USB video (`ENT_CODEC_*`, `API_USB_VIDEO`) — the F48 poster
  reported these did not work.

## General cautions reported by F48 sources

- E-Sys users report never to press "Code Default Values" and never to code a whole
  module folder (VO coding); back up before and after.
- E-Sys F48 users select target F056 (F48 is not offered as a PSdZ target in older data).
- BimmerCode required the full version for F48 coding; a 2019 BDC software release
  temporarily blocked BDC coding in BimmerCode until an app update.

## Sources

- BimmerCode F48 supported options: https://bimmercode.app/cars/f48/
- BimmerCode F30: https://bimmercode.app/cars/f30/
- BimmerCode F20: https://bimmercode.app/cars/f20/
- BimmerCode F15: https://bimmercode.app/cars/f15/
- BimmerCode G20: https://bimmercode.app/cars/g20/
- BimmerCode G01: https://bimmercode.app/cars/g01/
- BimmerCode G05: https://bimmercode.app/cars/g05/
- ma-bmw.com "[Tuto] Codage F48" (E-Sys, F48 BDC/KOMBI/HU_NBT entries with results):
  https://www.ma-bmw.com/forum/viewtopic.php?p=890184 and
  https://www.ma-bmw.com/forum/viewtopic.php?p=915819
- ma-bmw.com "[Tuto] Codage F48" (target F056, RAM 1024): https://www.ma-bmw.com/forum/viewtopic.php?p=890274,
  https://www.ma-bmw.com/forum/viewtopic.php?p=884685
- ma-bmw.com "[Tuto] Codage special F3X" (BC_DIGITAL_V, PIM_Driving_Text, TCM_MSA_DEFAULT_OFF,
  SPEEDLOCK): https://ma-bmw.com/forum/viewtopic.php?p=517621
- ma-bmw.com digital speed thread (F48 cluster via BimmerCode OK, HU not):
  https://ma-bmw.com/forum/viewtopic.php?p=1097329
- ma-bmw.com X4 video-in-motion thread (FF vs 3F): https://ma-bmw.com/forum/viewtopic.php?p=610163
- F15 coding guide spreadsheet (BDC_BODY 3051/3056/3068/3069/3110, HU_NBT 3000/3001, IHKA 3002):
  https://docs.google.com/spreadsheets/d/1UreLsK1PwycTWeW6OL71HOoVpLtKtfwRMRSvlsiC8JY/edit
- F15 coding list (Scribd): https://www.scribd.com/document/511882924/F15-Coding-Guide-Coding-List
- bmwfaq.org "Técnica Coding X1 (F48)" (3020 TCM_LOGIC_R_OFF_DOOR, 3069 PIA_DEFAULT_TIPPBLINKEN;
  page content not directly fetchable, cited via search snippets):
  https://www.bmwfaq.org/threads/coding-x1-f48.883241/post-17916658
- bmwfaq.org "Problema error esys" (F48 → F56 target): https://bmwfaq.org/threads/problema-error-esys.885664/
- bmwfaq.org Bluetooth ampliado thread (BDC cars need "Read (ECU)"; ENTRYNAV coding):
  https://www.bmwfaq.org/threads/duda-codificando-bluetooth-ampliado.925888/post-16298936
- f48.bimmerpost ENTRYNAV/ENTRYNAV2 and HU_NBT naming (search snippets; site refused direct fetch):
  https://f48.bimmerpost.com/forums/showthread.php?p=24580080,
  https://f48.bimmerpost.com/forums/showthread.php?p=27195512
- f48.bimmerpost cheat-sheet request / shared ECUs with F15/F56/I01 (search snippet):
  https://f48.bimmerpost.com/forums/showthread.php?p=24315986
- g05.bimmerpost E-Sys cheat codes (FH_TUERAUF_STOP_MAUT, TCM_MSA_Memory in DME):
  https://g05.bimmerpost.com/beta/showthread/1637597/g05-e-sys-cheat-codes/page/20
- BMW X3 TSB, digital speed missing after programming:
  https://www.carcomplaints.com/BMW/X3/2019/tsb/tsb-b620719.shtml

Not fetched / not checked: BimmerCode pages for F25 and G30; bimmerpost pages (connection
refused); Scribd document bodies (truncated).
