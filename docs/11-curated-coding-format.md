# Curated Coding Database Format

> **2026-10-28 review:** Historical research/design, with unverified or contradicted claims.
> See [document status](README.md) and [protocol corrections](20-protocol-evidence.md).
> Completion labels and code examples below are not validated vehicle contracts.
> Live coded bytes, data-group boundaries and multi-function masks must be matched to the exact variant.

> **Source:** BimmerCode decrypted root index `.enc` files (e.g., `00000069.enc`, `00001082.enc`)

---

## Database Architecture

The curated coding database is a three-layer system:

```
Layer 1: Root index .enc files     →  "BC_DIGITAL_V" at SECTION:BOARD_COMPUTER
Layer 2: CAFD variant .enc files   →  "BC_DIGITAL_V" byte 0x00 mask 0x01 value 0x01
Layer 3: .strings files            →  "BC_DIGITAL_V" = "Digital speed in board computer"
```

---

## Layer 1: Root Index Format

Each root index `.enc` file (named by CAFD ID, e.g., `00000069.enc`, `00001082.enc`)
defines curated coding presets for one ECU family.

```json
[
  {
    "section": "BOARD_COMPUTER",
    "name": "BC_DIGITAL_V",
    "descriptionText": "BC_DIGITAL_V_DESCRIPTION",
    "values": [
      {
        "name": "ACTIVE",
        "functions": [
          {
            "name": "BC_DIGITAL_V",
            "values": [{"value": "0x01", "position": "0"}]
          }
        ]
      },
      {
        "name": "NOT_ACTIVE",
        "functions": [
          {
            "name": "BC_DIGITAL_V",
            "values": [{"value": "0x00", "position": "0"}]
          }
        ]
      }
    ]
  },
  {
    "section": "BOARD_COMPUTER",
    "name": "DIGIT_GESCHW_ENABLE",
    "descriptionText": "DIGIT_GESCHW_ENABLE_DESCRIPTION",
    "values": [
      {
        "name": "KMH",
        "functions": [
          {"name": "DIGITAL_TACHO_ENABLE", "values": [{"value": "0x03", "position": "0"}]}
        ]
      },
      {
        "name": "MPH",
        "functions": [
          {"name": "DIGITAL_TACHO_ENABLE", "values": [{"value": "0x04", "position": "0"}]}
        ]
      }
    ]
  }
]
```

### Field Reference

| Field | Description |
|-------|-------------|
| `section` | UI category for grouping (BOARD_COMPUTER, HUD, ANGEL_EYES, etc.) |
| `name` | Coding option key — matches `.strings` key |
| `descriptionText` | Matches `.strings` description key (name + "_DESCRIPTION") |
| `values[]` | List of user-selectable options |
| `values[].name` | Value label — matches `.strings` value key (ACTIVE, NOT_ACTIVE, 5_KMH) |
| `values[].functions[]` | CAFD functions to modify when this value is selected |
| `values[].functions[].name` | CAFD function name — matches Layer 2 |
| `values[].functions[].values[]` | Hex value to write at the given position |

---

## Layer 2: CAFD Variant Format

Each CAFD variant `.enc` file (e.g., `000024C3-008-005-000.enc`) defines
the full technical parameter layout.

```json
{
  "dataGroups": [
    {
      "name": "LmmB",
      "dataGroupClass": "USER",
      "address": "0x3004",
      "functions": [
        {
          "name": "DRL_Idx",
          "storageInfo": {"start": "0", "end": "9", "mask": "0b11111111"},
          "params": [
            {
              "paramName": "F020Wert",
              "values": [{"value": "0x03", "position": "0"}]
            },
            {
              "paramName": "F030Wert",
              "values": [{"value": "0x01", "position": "0"}]
            }
          ]
        }
      ]
    }
  ]
}
```

### Field Reference

| Field | Description |
|-------|-------------|
| `dataGroups[].name` | Functional group name (System, LmmB, Led1, AHL) |
| `dataGroups[].address` | Memory address prefix for this group (hex string) |
| `functions[].name` | Parameter name (LWR_ENABLE, DRL_Idx, POLI1_Idx) |
| `functions[].storageInfo.start` | Starting byte position in the CAFD data |
| `functions[].storageInfo.end` | Ending byte position (inclusive) |
| `functions[].storageInfo.mask` | Bit mask within the byte (`0b00001111` = lower nibble) |
| `functions[].params[]` | Per-vehicle-variant values |
| `functions[].params[].paramName` | Platform code (F020=F20, F030=F30, F010=F10, F045=F45, F015=F15) |
| `functions[].params[].values[]` | Factory default values per platform variant |

### Bit Mask Notation

| Mask String | Binary | Meaning |
|-------------|--------|---------|
| `0b00000001` | Bit 0 | Single bit flag |
| `0b00001111` | Bits 0-3 | Lower nibble (4 bits) |
| `0b11110000` | Bits 4-7 | Upper nibble (4 bits) |
| `0b00001100` | Bits 2-3 | Bits 2-3 only |
| `0b11111111` | All 8 bits | Full byte |

---

## Layer 3: Translation Strings

The `.strings` files provide human-readable labels in Apple `.strings` format.

```
"BC_DIGITAL_V" = "Digital speed in board computer";
"BC_DIGITAL_V_DESCRIPTION" = "Enable/disable the display of the digital speed...";
"ACTIVE" = "Active";
"NOT_ACTIVE" = "Not active";
"5_KMH" = "5 km/h";
"BMW_LOGO" = "BMW logo";
"BMW_LOGO_M3" = "M3 logo";
```

---

## How to Use: End-to-End Coding Flow

### 1. Vehicle Connected → Get Supported ECUs

```python
vin = read_vin()                    # UDS 0x22 DID 0xF190
svt = read_svt()                    # UDS 0x22 from ZGW
model = decode_vin(vin)             # "F30" from "WBA3E32..."
```

### 2. Match ECU to Root Index

```python
# From SVT: FEM_BODY at 0x40, CAFD: 000024C3, variant: 008-005-000
cafd_id = "000024C3"

# Load root index
root = load_json(f"{cafd_id}.enc")  # The curated coding presets

# Load CAFD variant (for expert mode byte positions)
cafd = load_json(f"{cafd_id}-008-005-000.enc")  # Full parameter layout
```

### 3. Read Current CAFD from Car

```python
# Read current coding data from the ECU
current_cafd_hex = uds_read_did(ecu_address, CAFD_DID)
current_bytes = bytes.fromhex(current_cafd_hex)
```

### 4. Display Coding Options

```python
for preset in root:
    section = preset["section"]      # "BOARD_COMPUTER"
    name = preset["name"]            # "BC_DIGITAL_V"
    
    # Look up human-readable label
    label = strings.get(name, name)
    description = strings.get(preset["descriptionText"], "")
    
    # Determine current value
    current_value = None
    for value_option in preset["values"]:
        for func in value_option["functions"]:
            func_name = func["name"]
            # Find this function in the CAFD layout
            func_def = cafd_find_function(cafd, func_name)
            if func_def is None:
                continue
            
            # Extract current byte at the function's position
            byte_pos = int(func_def["storageInfo"]["start"])
            mask = parse_mask(func_def["storageInfo"]["mask"])
            current_byte = current_bytes[byte_pos] & mask
            
            # Check if this matches the value option
            expected_value = int(value_option["functions"][0]["values"][0]["value"], 16)
            if current_byte == expected_value:
                current_value = value_option["name"]
                break
    
    # Show in UI
    display_coding_option(
        section=section,
        name=label,
        description=description,
        current=current_value,
        options=[v["name"] for v in preset["values"]]
    )

def parse_mask(mask_str):
    """Parse '0b00001111' → 0x0F"""
    return int(mask_str.replace("0b", ""), 2)
```

### 5. Write Changed Coding

```python
# User selects "NOT_ACTIVE" for "BC_DIGITAL_V"
selected_preset = find_preset(root, "BC_DIGITAL_V")
selected_value = find_value(selected_preset, "NOT_ACTIVE")

# Build the write payload
modified_bytes = bytearray(current_bytes)
for func in selected_value["functions"]:
    func_name = func["name"]
    func_def = cafd_find_function(cafd, func_name)
    
    byte_pos = int(func_def["storageInfo"]["start"])
    mask = parse_mask(func_def["storageInfo"]["mask"])
    new_value = int(func["values"][0]["value"], 16)
    
    # Clear masked bits, set new value
    modified_bytes[byte_pos] &= ~mask
    modified_bytes[byte_pos] |= (new_value << trailing_zeros(mask))

# Write back to ECU
modified_hex = modified_bytes.hex()
uds_write_did(ecu_address, CAFD_WRITE_DID, bytes.fromhex(modified_hex))
```

---

## Complete Section Reference

Root index files define curated presets grouped by section:

| Section | Example Presets |
|---------|----------------|
| BOARD_COMPUTER | BC_DIGITAL_V, BC_DATUM, BC_LEERZEILE, DIGIT_GESCHW_ENABLE |
| HUD | HUD_ENTERTAINMENT_ENABLE, HUD_TELEFONBUCH_ENABLE |
| INSTRUMENT_CLUSTER | MPM_ENABLE, BMW_LOGO, LAYOUT |
| DAYTIME_RUNNING_LIGHTS | DRL_MODUS, TAGFAHRL_V_PART_OF_WL, DRL_REAR |
| ANGEL_EYES | ANGEL_EYES_BRIGHTNESS, PARKING_LIGHTS_BRIGHTNESS |
| COMFORT_OPENING_CLOSING | KOMFORTOEFFNUNG_FB, KOMFORTSCHLIESSUNG_FB |
| MIRRORS | ASP_BORDSTEINAUTOMATIK, ASP_AUSKLAPPEN_NACH_KOMFORTSCHLIESSEN |
| START_STOP_FUNCTION | TCM_MSA_MEMORY, TCM_MSA_DEFAULT_OFF |
| INDICATOR | BLINKZYKLEN_ANZAHL_TIPP, QUITTBLK_SICHERN_ANZAHL |
| ACOUSTICAL_CONFIRMATION | ACOUSTICAL_LOCK_CONFIRMATION |
| AIR_CONDITIONING | AC_ON_WITH_AUTO, MEMORY_OFF, MEMORY_UMLUFT |
| ACTIVE_SOUND_DESIGN | ASD_INSIDE, ASD_ACTIVE |
| HEADLIGHT_CLEANING | WW_SCHEINWERFERREINIGUNG |
| WIPE_WASH | WW_STANDRUECKSCHALTUNG |
| TAILGATE | HKL_ROCKERSWITCHPOS1_BUTTON_TYPE, SCH_FBD |
| PDC | V_SCHWELLE_1, D_SCHWELLE_1 |
| DRIVING_ASSISTANCE | ROAD_EDGE_WARNING_ENABLED |
| SEAT_BELT_REMINDER | SEAT_BELT_REMINDER_DRIVER, SEAT_BELT_REMINDER_PASSENGER |
| SEAT_HEATING | SA_MEMORY_ZEIT |
| SIDE_VIEW_CAMERA | SV_Activate_Speed_Limit |
| CORNERING_LIGHTS | Cornering light parameters through LmmA/LmmB functions |
| AMBIENT_LIGHTING | Ambient light color/contour through LED functions |
| EMERGENCY_STOP_SIGNAL | BFD parameters through Led groups |
| WELCOME_LIGHT | WL_FUNKTION_KZL, WL_HELLIGKEIT through LmmX functions |

---

## SALAPA Filtering

Some presets include a `series` filter for engine type:

```json
{
  "series": ["gasoline"],
  "section": "ACTIVE_SOUND_DESIGN",
  "name": "ASD_INSIDE",
  ...
}
```

The `salapa.enc` database (5,640 entries) maps SALAPA option codes to
human-readable names and can be used to filter coding options based on
the vehicle's factory equipment.