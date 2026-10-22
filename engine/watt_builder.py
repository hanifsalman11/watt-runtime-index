import os
import json
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# ==========================================
# ENVIRONMENT CONFIGURATION
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://USERNAME.github.io/watt-runtime-index").rstrip("/")
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "e4f3d2c1b0a9f8e7d6c5b4a3f2e1d0c9").strip()
CUSTOM_APPLIANCE = os.environ.get("CUSTOM_APPLIANCE", "").strip()
PAGES_PER_RUN = int(os.environ.get("PAGES_PER_RUN", "3"))

DOCS_DIR = "docs"
DATA_DIR = "data"
PUBLISHED_FILE = os.path.join(DATA_DIR, "published_appliances.json")
MONETIZATION_FILE = os.path.join(DATA_DIR, "monetization.json")

# Daftar perangkat berdaya beli tinggi (High-Ticket Backup Power & Off-Grid Intent)
SEED_APPLIANCES = [
    ("1/2 HP Basement Sump Pump", 800, 2100, 0.25, "Emergency Home Backup"),
    ("CPAP Machine with Heated Humidifier", 65, 90, 1.0, "Medical & Camping"),
    ("7 Cu Ft Chest Freezer", 90, 600, 0.35, "Food Preservation & Outage"),
    ("Full-Size 20 Cu Ft Kitchen Refrigerator", 180, 1200, 0.40, "Home Kitchen Backup"),
    ("Starlink Standard Gen 3 Satellite Dish", 75, 110, 0.85, "Off-Grid & RV Internet"),
    ("5000 BTU Window Air Conditioner", 500, 1500, 0.65, "Cooling & RV Climate"),
    ("1500W Portable Ceramic Space Heater", 1500, 1500, 0.80, "Winter Heating"),
    ("Pellet Stove Auger & Blower Fan", 130, 520, 0.70, "Off-Grid Winter Heating"),
    ("1/3 HP Garage Door Opener", 400, 1100, 0.05, "Home Utility Backup"),
    ("1000W Countertop Microwave Oven", 1200, 1800, 0.15, "Kitchen & Camper Cooking"),
    ("High-End Gaming PC with RTX GPU", 450, 750, 1.0, "Workstation & Electronics"),
    ("1/2 HP Deep Well Submersible Water Pump", 1000, 2800, 0.20, "Off-Grid Water Supply"),
    ("Portable Oxygen Concentrator", 120, 180, 1.0, "Critical Medical Backup"),
    ("RV 13500 BTU Rooftop Air Conditioner", 1350, 3200, 0.60, "RV & Motorhome"),
    ("Dual-Boiler Home Espresso Machine", 1400, 1600, 0.20, "Kitchen & Mobile Coffee"),
    ("40-pint Basement Dehumidifier", 420, 1100, 0.75, "Basement Moisture Control"),
    ("12V Portable Car Fridge Freezer (45L)", 45, 90, 0.35, "Overlanding & Camping"),
    ("Home Gas Furnace Blower Motor", 600, 1800, 0.50, "Winter Emergency Heating"),
    ("Electric Induction Cooktop Burner", 1800, 1800, 0.30, "Vanlife & Off-Grid Cooking"),
    ("75-Gallon Aquarium Heater & Canister Filter", 260, 310, 0.65, "Pet & Aquarium Backup"),
    ("Home CPAP BiPAP Machine (No Heat)", 35, 60, 1.0, "Medical & Travel"),
    ("Corded 15-Amp Circular Saw", 1800, 3200, 0.25, "Jobsite Power Tools"),
    ("120V Tankless Gas Water Heater Igniter", 65, 150, 0.30, "Home Plumbing Backup"),
    ("55-Inch 4K OLED Television & Soundbar", 160, 220, 1.0, "Home Entertainment"),
    ("Portable Evaporative Swamp Cooler", 220, 650, 0.85, "Off-Grid Cooling"),
    ("Electric Blanket (Queen Size Dual Zone)", 160, 160, 0.60, "Winter Camping & Sleep"),
    ("1/4 HP Sewage Ejector Pump", 650, 1750, 0.15, "Basement Plumbing"),
    ("Commercial Food Truck Panini Press", 1650, 1650, 0.65, "Mobile Catering"),
    ("Home NAS Server & Wi-Fi 7 Mesh Router", 55, 95, 1.0, "IT & Home Lab"),
    ("Portable Baby Bottle Warmer & Sterilizer", 500, 550, 0.15, "Travel & Family")
]


def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] JSON read notice on {filepath}: {e}")
    return default


def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"[\s-]+", "-", text).strip("-")


def safe_float(val, default=100.0):
    try:
        cleaned = re.sub(r"[^0-9.]", "", str(val))
        return float(cleaned) if cleaned else float(default)
    except Exception:
        return float(default)


def build_amazon_url(search_keywords, mon_cfg):
    domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")
    encoded_q = urllib.parse.quote_plus(search_keywords)
    return f"https://{domain}/s?k={encoded_q}&tag={tag}"


def discover_google_appliance_queries():
    """Mengambil ide pencarian perangkat listrik berdaya beli tinggi dari Google Autocomplete US."""
    discovered = []
    seeds = [
        "how many watts does a ",
        "what size solar generator to run a ",
        "battery backup for "
    ]
    for seed in seeds:
        try:
            url = f"http://suggestqueries.google.com/complete/search?client=firefox&hl=en&gl=us&q={urllib.parse.quote(seed)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for suggestion in data[1]:
                    cleaned = suggestion.lower()
                    for prefix in seeds:
                        cleaned = cleaned.replace(prefix, "")
                    cleaned = re.sub(r"\b(use|need|require|take|on|wattage|watts|per hour|to run)\b", "", cleaned).strip()
                    if 4 <= len(cleaned) <= 38:
                        discovered.append((cleaned.title(), 350, 900, 0.65, "Home & Off-Grid Power"))
        except Exception as e:
            print(f"[WARN] Suggest query notice: {e}")
    return discovered


def build_deterministic_engineering_data(appliance_tuple):
    """Mesin cadangan (100% bebas gagal) berbasis rumus teknik elektro jika API Gemini limit."""
    name, run_w, surge_w, duty, category = appliance_tuple
    effective_hourly_wh = round(run_w * duty, 1)
    eight_hr_wh = int(round((effective_hourly_wh * 8) / 0.85))

    if surge_w >= 1800 or eight_hr_wh >= 1800:
        tier_station = "2048Wh 2400W LiFePO4 Portable Power Station Solar Generator"
        tier_price = "$999 - $1,599"
        solar_rec = "400W Portable Folding Monocrystalline Solar Panel"
        solar_price = "$349 - $549"
    elif surge_w >= 1000 or eight_hr_wh >= 750:
        tier_station = "1024Wh 1800W LiFePO4 Portable Power Station"
        tier_price = "$499 - $799"
        solar_rec = "200W Foldable Portable Solar Panel Charger"
        solar_price = "$189 - $299"
    else:
        tier_station = "512Wh 800W LiFePO4 Portable Power Station Battery Backup"
        tier_price = "$249 - $399"
        solar_rec = "100W Portable Folding Solar Panel Kit"
        solar_price = "$99 - $169"

    return {
        "appliance_name": name,
        "category": category,
        "seo_title": f"{name} Wattage, Runtime Calculator & Solar Generator Sizing (2026)",
        "meta_description": f"Calculate exact running watts ({run_w}W), starting surge watts ({surge_w}W), and battery backup runtime for a {name}. Find the right LiFePO4 power station size.",
        "specs": {
            "running_watts": run_w,
            "starting_surge_watts": surge_w,
            "duty_cycle_factor": duty,
            "recommended_battery_wh": max(512, eight_hr_wh),
            "recommended_inverter_watts": max(500, int(round(surge_w * 1.2, -2))),
            "voltage_std": "120V AC (60Hz) Pure Sine Wave"
        },
        "engineering_verdict": f"A typical {name} draws {run_w}W continuously with a momentary startup surge of {surge_w}W. Factoring in a {int(duty*100)}% compressor/motor duty cycle and 85% pure sine wave inverter efficiency, an 8-hour outage requires at least {max(512, eight_hr_wh)}Wh of LiFePO4 battery capacity.",
        "hardware_recommendations": [
            {
                "role": "Primary Battery Backup / Solar Generator",
                "product_title": tier_station,
                "price_range": tier_price,
                "amazon_query": tier_station,
                "why_needed": f"Handles the {surge_w}W startup inrush current and delivers {max(512, eight_hr_wh)}Wh+ for extended runtime."
            },
            {
                "role": "Recommended Off-Grid Solar Charging Array",
                "product_title": solar_rec,
                "price_range": solar_price,
                "amazon_query": solar_rec,
                "why_needed": f"Replenishes daily watt-hour draw in 4 to 5 hours of peak sunlight during multi-day grid outages."
            },
            {
                "role": "Plug-In Wattage & KWh Energy Monitor",
                "product_title": "Digital Kill-A-Watt Electricity Usage Monitor Plug",
                "price_range": "$18 - $32",
                "amazon_query": "Kill A Watt Electricity Usage Monitor Wattage Meter",
                "why_needed": f"Measure the exact real-time amp and watt draw of your specific {name} model before sizing your battery bank."
            }
        ],
        "optimization_tips": [
            f"Always use a Pure Sine Wave inverter when running a {name} to prevent AC motor overheating, transformer hum, and premature circuit board failure.",
            f"Account for the {surge_w}W starting surge: inductive motors and compressors briefly draw 2x to 3x their running wattage for the first 500 milliseconds.",
            "Keep LiFePO4 battery banks between 10% and 90% State of Charge (SoC) in room-temperature conditions to achieve 3,000+ lifecycle charges."
        ],
        "faqs": [
            {
                "q": f"How many watts does a {name} use per hour?",
                "a": f"While active, a {name} consumes {run_w} watts ({round(run_w/120, 2)} Amps at 120V). With a typical {int(duty*100)}% duty cycle, it uses approximately {effective_hourly_wh} watt-hours (Wh) per clock hour."
            },
            {
                "q": f"Can a 1000Wh portable power station run a {name}?",
                "a": f"A 1000Wh LiFePO4 power station (delivering ~850Wh of usable AC power after inverter conversion) will run a {name} for approximately {round(850 / max(10, effective_hourly_wh), 1)} hours, provided its inverter surge rating exceeds {surge_w}W."
            },
            {
                "q": f"What size solar panel do I need to run a {name} off-grid?",
                "a": f"To offset the {effective_hourly_wh}Wh hourly consumption during daytime operation while recharging your battery bank, pair your power station with at least a {solar_rec}."
            }
        ]
    }


def generate_appliance_data(appliance_tuple):
    """Memanggil Gemini 2.5 Flash API; jika gagal otomatis memakai Deterministic Engineering Engine."""
    if not GEMINI_API_KEY:
        return build_deterministic_engineering_data(appliance_tuple)

    name, run_w, surge_w, duty, category = appliance_tuple
    prompt = f"""
You are a Senior Off-Grid Solar & Electrical Engineer. Create an accurate 2026 power consumption, battery backup sizing, and solar generator guide for: "{name}".
Baseline reference specs: Running Watts ~{run_w}W, Starting Surge Watts ~{surge_w}W, Duty Cycle ~{duty}.
Return ONLY a valid JSON object matching this exact schema:
{{
  "appliance_name": "{name}",
  "category": "{category}",
  "seo_title": "{name} Wattage, Runtime Calculator & Solar Generator Sizing (2026)",
  "meta_description": "Calculate exact running watts, starting surge watts, and battery backup runtime for a {name}. Find the exact LiFePO4 solar generator size required.",
  "specs": {{
    "running_watts": {run_w},
    "starting_surge_watts": {surge_w},
    "duty_cycle_factor": {duty},
    "recommended_battery_wh": 1024,
    "recommended_inverter_watts": 1800,
    "voltage_std": "120V AC Pure Sine Wave"
  }},
  "engineering_verdict": "3-sentence technical summary explaining running watts, surge watts, and how many Watt-hours are needed for an 8-hour power outage.",
  "hardware_recommendations": [
    {{
      "role": "Primary Battery Backup / Solar Generator",
      "product_title": "Exact capacity LiFePO4 Portable Power Station name",
      "price_range": "$499 - $899",
      "amazon_query": "Search keywords for Amazon",
      "why_needed": "1-sentence engineering explanation"
    }},
    {{
      "role": "Recommended Off-Grid Solar Array",
      "product_title": "Exact wattage Portable Folding Solar Panel",
      "price_range": "$189 - $349",
      "amazon_query": "Search keywords for Amazon",
      "why_needed": "1-sentence explanation"
    }},
    {{
      "role": "Diagnostic Watt Meter & Surge Protector",
      "product_title": "Digital Plug-In Wattage & KWh Energy Monitor",
      "price_range": "$18 - $32",
      "amazon_query": "Kill A Watt Electricity Usage Monitor",
      "why_needed": "1-sentence explanation"
    }}
  ],
  "optimization_tips": [
    "Tip 1 for extending battery runtime",
    "Tip 2 regarding inverter surge and efficiency",
    "Tip 3 regarding solar recharging"
  ],
  "faqs": [
    {{"q": "How many watts does a {name} use?", "a": "Detailed answer with amps and watt-hours."}},
    {{"q": "Can a portable power station run a {name} overnight?", "a": "Detailed runtime calculation answer."}},
    {{"q": "Do I need a pure sine wave inverter for a {name}?", "a": "Detailed technical answer."}}
  ]
}}
"""

    for model_name in ["gemini-2.5-flash", "gemini-2.0-flash"]:
        try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.25,
                    "responseMimeType": "application/json"
                }
            }
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=35) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)
                parsed = json.loads(raw_text)
                if "specs" in parsed and "hardware_recommendations" in parsed:
                    return parsed
        except Exception as e:
            print(f"[WARN] Gemini ({model_name}) fallback notice for '{name}': {e}")

    return build_deterministic_engineering_data(appliance_tuple)


def build_appliance_html_page(data, slug, mon_cfg):
    app_name = data.get("appliance_name", "Appliance")
    sp = data.get("specs", {})
    run_w = int(safe_float(sp.get("running_watts", 300), 300))
    surge_w = int(safe_float(sp.get("starting_surge_watts", 600), 600))
    duty_pct = int(round(safe_float(sp.get("duty_cycle_factor", 0.5), 0.5) * 100))
    duty_pct = max(5, min(100, duty_pct))
    rec_wh = int(safe_float(sp.get("recommended_battery_wh", 1024), 1024))
    rec_inv = int(safe_float(sp.get("recommended_inverter_watts", 1500), 1500))

    top_banner = mon_cfg.get("top_cta_banner", {})
    top_banner_url = build_amazon_url(top_banner.get("search_query", "LiFePO4+Solar+Generator"), mon_cfg)

    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "name": f"{app_name} Battery Runtime & Solar Sizing Calculator",
                "applicationCategory": "UtilitiesApplication",
                "operatingSystem": "Web Browser",
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f.get("q", ""),
                        "acceptedAnswer": {"@type": "Answer", "text": f.get("a", "")}
                    } for f in data.get("faqs", [])
                ]
            }
        ]
    }

    hw_html = ""
    for hw in data.get("hardware_recommendations", []):
        amz_url = build_amazon_url(hw.get("amazon_query", hw.get("product_title", "LiFePO4 Power Station")), mon_cfg)
        hw_html += f"""
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-cyan-500/50 transition">
          <div>
            <div class="flex items-center justify-between gap-2 mb-2">
              <span class="text-xs font-bold uppercase tracking-wider bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 px-2.5 py-0.5 rounded">{hw.get('role', 'Recommended Hardware')}</span>
              <span class="text-sm font-bold text-emerald-400">{hw.get('price_range', '$299+')}</span>
            </div>
            <h3 class="text-lg font-bold text-white mt-2">{hw.get('product_title', 'LiFePO4 Power Station')}</h3>
            <p class="text-xs text-slate-400 mt-2 leading-relaxed">⚡ {hw.get('why_needed', '')}</p>
          </div>
          <a href="{amz_url}" target="_blank" rel="nofollow sponsored" class="mt-5 block text-center bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-extrabold py-2.5 px-4 rounded-lg text-sm transition shadow-lg">
            Check Price & Specs on Amazon →
          </a>
        </div>"""

    tips_html = "".join([
        f"<li class='flex items-start gap-3 bg-slate-900/90 border border-slate-800 p-4 rounded-xl text-sm text-slate-200'><span class='text-cyan-400 font-bold'>⚡</span><span>{t}</span></li>"
        for t in data.get("optimization_tips", [])
    ])

    faqs_html = "".join([
        f"<div class='bg-slate-900 border border-slate-800 rounded-xl p-5'><h3 class='font-bold text-white text-base mb-2'>{f.get('q', '')}</h3><p class='text-sm text-slate-300 leading-relaxed'>{f.get('a', '')}</p></div>"
        for f in data.get("faqs", [])
    ])

    canonical_url = f"{SITE_BASE_URL}/{slug}.html"

    html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{data.get('seo_title', app_name)}</title>
  <meta name="description" content="{data.get('meta_description', '')}">
  <link rel="canonical" href="{canonical_url}">
  <meta property="og:title" content="{data.get('seo_title', app_name)}">
  <meta property="og:description" content="{data.get('meta_description', '')}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical_url}">
  <script src="https://cdn.tailwindcss.com"></script>
  <script type="application/ld+json">{json.dumps(schema_graph)}</script>
</head>
<body class="bg-slate-950 text-slate-100 antialiased min-h-screen flex flex-col">
  <header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-30">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <a href="index.html" class="text-lg font-black tracking-tight text-white flex items-center gap-2">
        <span class="bg-cyan-500 text-slate-950 px-2 py-0.5 rounded font-black">WATT</span>RuntimeIndex
      </a>
      <a href="{top_banner_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {top_banner.get('cta_text', 'Compare Solar Generators →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-10 flex-1 w-full">
    <div class="mb-8">
      <div class="flex flex-wrap items-center gap-2.5 mb-3">
        <span class="text-xs font-extrabold uppercase tracking-widest bg-cyan-500 text-slate-950 px-3 py-1 rounded-full">{data.get('category', 'Power Sizing')}</span>
        <span class="text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 px-3 py-1 rounded-full">Running: {run_w}W | Surge: {surge_w}W</span>
        <span class="text-xs font-semibold bg-slate-800 text-slate-300 px-3 py-1 rounded-full">{sp.get('voltage_std', '120V AC')}</span>
      </div>
      <h1 class="text-3xl sm:text-4xl font-black text-white leading-tight">{data.get('seo_title', app_name)}</h1>
      <div class="mt-4 bg-slate-900 border-l-4 border-cyan-500 p-4 rounded-r-xl text-sm text-slate-200 leading-relaxed">
        <strong>Electrical Engineering Summary:</strong> {data.get('engineering_verdict', '')}
      </div>
    </div>

    <!-- INTERACTIVE RUNTIME & SOLAR SIZING CALCULATOR -->
    <section class="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 mb-12 shadow-2xl">
      <h2 class="text-xl font-extrabold text-white mb-2">Interactive {app_name} Battery Runtime & Solar Calculator</h2>
      <p class="text-xs text-slate-400 mb-6">Adjust battery capacity (Watt-hours), appliance wattage, and duty cycle to calculate exact backup runtime and solar panel recharge speed.</p>

      <div class="grid md:grid-cols-2 gap-8 items-center">
        <div class="space-y-5">
          <div>
            <div class="flex justify-between text-sm font-medium mb-1.5">
              <label for="whSlider" class="text-slate-300">Power Station / Battery Capacity (Wh)</label>
              <span class="text-cyan-400 font-bold"><span id="whVal">{rec_wh}</span> Wh</span>
            </div>
            <input id="whSlider" type="range" min="256" max="5120" step="128" value="{rec_wh}" class="w-full accent-cyan-500 cursor-pointer">
          </div>

          <div>
            <div class="flex justify-between text-sm font-medium mb-1.5">
              <label for="wattSlider" class="text-slate-300">{app_name} Running Watts (W)</label>
              <span class="text-cyan-400 font-bold"><span id="wattVal">{run_w}</span> W</span>
            </div>
            <input id="wattSlider" type="range" min="15" max="2400" step="5" value="{run_w}" class="w-full accent-cyan-500 cursor-pointer">
          </div>

          <div>
            <div class="flex justify-between text-sm font-medium mb-1.5">
              <label for="dutySlider" class="text-slate-300">Compressor / Motor Duty Cycle (%)</label>
              <span class="text-cyan-400 font-bold"><span id="dutyVal">{duty_pct}</span>%</span>
            </div>
            <input id="dutySlider" type="range" min="10" max="100" step="5" value="{duty_pct}" class="w-full accent-cyan-500 cursor-pointer">
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="bg-slate-950 border border-cyan-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-cyan-400 font-bold">Estimated Runtime</span>
            <div class="text-2xl sm:text-3xl font-black text-white mt-1"><span id="runtimeHrs">0</span> <span class="text-sm font-normal text-slate-400">hrs</span></div>
            <p class="text-xs text-slate-500 mt-1">At 85% pure sine inverter efficiency</p>
          </div>

          <div class="bg-slate-950 border border-amber-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-amber-400 font-bold">24-Hr Energy Draw</span>
            <div class="text-2xl sm:text-3xl font-black text-amber-400 mt-1"><span id="dailyWh">0</span> <span class="text-sm font-normal text-slate-400">Wh/day</span></div>
            <p class="text-xs text-slate-500 mt-1">Min Inverter: <strong>{rec_inv}W Surge</strong></p>
          </div>
        </div>
      </div>

      <div class="mt-6 bg-cyan-950/40 border border-cyan-500/30 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div class="text-sm text-cyan-100 font-medium">
          ☀️ Minimum Solar Input to Run Indefinitely: <strong class="text-cyan-400 text-base"><span id="solarNeeded">200</span>W Solar Panel Array</strong> (assuming 4.5 peak sun hours).
        </div>
        <a id="dynamicStationBtn" href="{top_banner_url}" target="_blank" rel="nofollow sponsored" class="shrink-0 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-extrabold px-4 py-2.5 rounded-lg text-xs uppercase tracking-wider transition">
          Find <span id="btnWhText">{rec_wh}</span>Wh Power Station on Amazon →
        </a>
      </div>
    </section>

    <!-- HARDWARE RECOMMENDATIONS -->
    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">Recommended Solar Generators & Backup Hardware</h2>
        <span class="text-xs text-slate-400">Pure Sine Wave & LiFePO4 Verified</span>
      </div>
      <div class="grid md:grid-cols-3 gap-5">{hw_html}</div>
    </section>

    <!-- ELECTRICAL SPECIFICATIONS TABLE -->
    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-4">{app_name} Electrical Benchmark Specs</h2>
      <div class="overflow-x-auto bg-slate-900 border border-slate-800 rounded-xl">
        <table class="w-full text-left border-collapse text-sm">
          <tbody>
            <tr class="border-b border-slate-800">
              <th class="py-3.5 px-4 text-slate-400 font-medium">Continuous Running Wattage</th>
              <td class="py-3.5 px-4 font-bold text-white">{run_w} Watts ({round(run_w/120, 2)} Amps @ 120V)</td>
            </tr>
            <tr class="border-b border-slate-800">
              <th class="py-3.5 px-4 text-slate-400 font-medium">Peak Starting / Inrush Surge</th>
              <td class="py-3.5 px-4 font-bold text-amber-400">{surge_w} Watts</td>
            </tr>
            <tr class="border-b border-slate-800">
              <th class="py-3.5 px-4 text-slate-400 font-medium">Typical Operating Duty Cycle</th>
              <td class="py-3.5 px-4 font-bold text-cyan-400">{duty_pct}% ({round(run_w * (duty_pct/100), 1)} Wh per hour)</td>
            </tr>
            <tr>
              <th class="py-3.5 px-4 text-slate-400 font-medium">Recommended Minimum Inverter Rating</th>
              <td class="py-3.5 px-4 font-bold text-emerald-400">{rec_inv}W Continuous Pure Sine Wave</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- OPTIMIZATION TIPS -->
    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-4">Off-Grid & Outage Runtime Optimization Tips</h2>
      <ul class="space-y-3">{tips_html}</ul>
    </section>

    <!-- FAQ -->
    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-5">Frequently Asked Questions ({app_name})</h2>
      <div class="space-y-4">{faqs_html}</div>
    </section>
  </main>

  <footer class="border-t border-slate-800 py-8 text-center text-xs text-slate-500 px-4">
    <p>© {datetime.now(timezone.utc).year} WattRuntimeIndex. Independent Off-Grid & Backup Power Engineering Database. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const whSlider = document.getElementById('whSlider');
    const wattSlider = document.getElementById('wattSlider');
    const dutySlider = document.getElementById('dutySlider');
    const whVal = document.getElementById('whVal');
    const wattVal = document.getElementById('wattVal');
    const dutyVal = document.getElementById('dutyVal');
    const runtimeHrs = document.getElementById('runtimeHrs');
    const dailyWh = document.getElementById('dailyWh');
    const solarNeeded = document.getElementById('solarNeeded');
    const btnWhText = document.getElementById('btnWhText');

    function recalculate() {{
      const wh = parseFloat(whSlider.value);
      const watts = parseFloat(wattSlider.value);
      const duty = parseFloat(dutySlider.value) / 100.0;

      whVal.textContent = wh.toLocaleString();
      wattVal.textContent = watts.toLocaleString();
      dutyVal.textContent = Math.round(duty * 100);
      btnWhText.textContent = wh.toLocaleString();

      const usableWh = wh * 0.85;
      const effectiveWatts = Math.max(5, watts * duty);
      const hours = usableWh / effectiveWatts;
      const dayDraw = Math.round(effectiveWatts * 24);
      const recSolar = Math.max(100, Math.ceil((dayDraw / 4.0) / 50) * 50);

      runtimeHrs.textContent = hours.toFixed(1);
      dailyWh.textContent = dayDraw.toLocaleString();
      solarNeeded.textContent = recSolar.toLocaleString();
    }}

    whSlider.addEventListener('input', recalculate);
    wattSlider.addEventListener('input', recalculate);
    dutySlider.addEventListener('input', recalculate);
    recalculate();
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(html)


def rebuild_portal_sitemap_and_rss(published, mon_cfg):
    top_banner = mon_cfg.get("top_cta_banner", {})
    top_banner_url = build_amazon_url(top_banner.get("search_query", "LiFePO4+Solar+Generator"), mon_cfg)

    cards_html = ""
    for item in reversed(published):
        cards_html += f"""
        <a href="{item['slug']}.html" class="block bg-slate-900 border border-slate-800 hover:border-cyan-500/60 rounded-xl p-5 transition group">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-black uppercase bg-cyan-500 text-slate-950 px-2.5 py-0.5 rounded">{item.get('running_watts', 300)}W Run / {item.get('surge_watts', 600)}W Surge</span>
            <span class="text-xs text-slate-400">{item.get('category', 'Backup Power')}</span>
          </div>
          <h2 class="text-base font-bold text-white group-hover:text-cyan-400 transition">{item['appliance_name']} Runtime & Sizing Calculator</h2>
          <p class="text-xs text-slate-400 mt-2 line-clamp-2">{item['description']}</p>
          <span class="inline-block mt-4 text-xs font-extrabold text-cyan-400">Launch Wattage & Battery Calculator →</span>
        </a>"""

    index_html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WattRuntimeIndex — Appliance Wattage, Battery Backup & Solar Generator Calculator (2026)</title>
  <meta name="description" content="Calculate running watts, starting surge watts, and exact LiFePO4 portable power station runtime for home, RV, and emergency appliances.">
  <link rel="canonical" href="{SITE_BASE_URL}/">
  <link rel="alternate" type="application/rss+xml" title="WattRuntimeIndex RSS Feed" href="{SITE_BASE_URL}/rss.xml">
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col">
  <header class="border-b border-slate-800 bg-slate-900/80 sticky top-0 z-30 backdrop-blur">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <div class="text-lg font-black text-white flex items-center gap-2">
        <span class="bg-cyan-500 text-slate-950 px-2 py-0.5 rounded font-black">WATT</span>RuntimeIndex
      </div>
      <a href="{top_banner_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {top_banner.get('cta_text', 'Compare LiFePO4 Solar Generators →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-12 flex-1 w-full">
    <div class="text-center max-w-2xl mx-auto mb-10">
      <h1 class="text-3xl sm:text-5xl font-black text-white tracking-tight">Appliance Wattage & Solar Generator Sizing Database</h1>
      <p class="text-slate-400 mt-3 text-base sm:text-lg">Select any household, RV, or medical appliance below to calculate exact battery backup runtime (Wh) and required inverter surge capacity.</p>
      <div class="mt-6">
        <input id="filterInput" type="text" placeholder="Search appliance (e.g. Sump Pump, CPAP, Chest Freezer, Starlink, Refrigerator...)" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3.5 text-sm text-white focus:outline-none focus:border-cyan-500">
      </div>
    </div>

    <div id="applianceGrid" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">{cards_html}</div>
  </main>

  <footer class="border-t border-slate-800 py-8 text-center text-xs text-slate-500">
    <p>© {datetime.now(timezone.utc).year} WattRuntimeIndex. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const filterInput = document.getElementById('filterInput');
    const cards = Array.from(document.getElementById('applianceGrid').children);
    filterInput.addEventListener('input', (e) => {{
      const q = e.target.value.toLowerCase();
      cards.forEach(c => {{
        c.style.display = c.textContent.toLowerCase().includes(q) ? 'block' : 'none';
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls_xml = f"""  <url>
    <loc>{SITE_BASE_URL}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>\n"""

    for item in published:
        urls_xml += f"""  <url>
    <loc>{SITE_BASE_URL}/{item['slug']}.html</loc>
    <lastmod>{item.get('date', today)}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>\n"""

    with open(os.path.join(DOCS_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls_xml}</urlset>""")

    rss_items = ""
    for item in list(reversed(published))[:30]:
        rss_items += f"""    <item>
      <title>{item['title']}</title>
      <link>{SITE_BASE_URL}/{item['slug']}.html</link>
      <guid>{SITE_BASE_URL}/{item['slug']}.html</guid>
      <description>{item['description']}</description>
    </item>\n"""

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>WattRuntimeIndex Power & Solar Sizing Database</title>
    <link>{SITE_BASE_URL}/</link>
    <description>Interactive Appliance Wattage and LiFePO4 Solar Generator Calculators</description>
    <atom:link href="{SITE_BASE_URL}/rss.xml" rel="self" type="application/rss+xml" />
    <atom:link href="https://pubsubhubbub.appspot.com/" rel="hub" />
{rss_items}  </channel>
</rss>"""

    with open(os.path.join(DOCS_DIR, "rss.xml"), "w", encoding="utf-8") as f:
        f.write(rss_xml)

    with open(os.path.join(DOCS_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE_URL}/sitemap.xml\n")

    with open(os.path.join(DOCS_DIR, f"{INDEXNOW_KEY}.txt"), "w", encoding="utf-8") as f:
        f.write(INDEXNOW_KEY)


def notify_search_engines(new_urls):
    if not SITE_BASE_URL or not new_urls:
        return
    parsed_host = urllib.parse.urlparse(SITE_BASE_URL).netloc
    payload = {
        "host": parsed_host,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_BASE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": new_urls
    }
    try:
        req = urllib.request.Request(
            "https://api.indexnow.org/indexnow",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[INDEXNOW] Pushed {len(new_urls)} URLs (HTTP {resp.status})")
    except Exception as e:
        print(f"[WARN] IndexNow ping notice: {e}")

    try:
        hub_data = urllib.parse.urlencode({
            "hub.mode": "publish",
            "hub.url": f"{SITE_BASE_URL}/rss.xml"
        }).encode("utf-8")
        req_hub = urllib.request.Request(
            "https://pubsubhubbub.appspot.com/",
            data=hub_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        with urllib.request.urlopen(req_hub, timeout=15) as resp_hub:
            print(f"[WEBSUB] Google PubSubHubbub ping status: {resp_hub.status}")
    except Exception as e:
        print(f"[WARN] WebSub ping notice: {e}")


def main():
    published = load_json(PUBLISHED_FILE, [])
    mon_cfg = load_json(MONETIZATION_FILE, {})
    published_slugs = {item["slug"] for item in published}

    candidates = []
    if CUSTOM_APPLIANCE:
        candidates.append((CUSTOM_APPLIANCE.title(), 400, 1000, 0.65, "Custom Power Guide"))
    candidates.extend(SEED_APPLIANCES)
    candidates.extend(discover_google_appliance_queries())

    new_urls = []
    count = 0

    for app_tuple in candidates:
        if count >= PAGES_PER_RUN:
            break
        app_name = app_tuple[0]
        slug = slugify(f"{app_name}-wattage-runtime-calculator")
        if slug in published_slugs:
            continue

        print(f"[ENGINE] Building wattage & solar calculator for: {app_name}...")
        try:
            data = generate_appliance_data(app_tuple)
            build_appliance_html_page(data, slug, mon_cfg)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            sp = data.get("specs", {})

            published.append({
                "appliance_name": data.get("appliance_name", app_name),
                "slug": slug,
                "title": data.get("seo_title", f"{app_name} Wattage Calculator"),
                "description": data.get("meta_description", ""),
                "category": data.get("category", "Backup Power"),
                "running_watts": int(safe_float(sp.get("running_watts", app_tuple[1]), app_tuple[1])),
                "surge_watts": int(safe_float(sp.get("starting_surge_watts", app_tuple[2]), app_tuple[2])),
                "date": today
            })
            published_slugs.add(slug)
            if SITE_BASE_URL:
                new_urls.append(f"{SITE_BASE_URL}/{slug}.html")
            count += 1
            time.sleep(2)
        except Exception as e:
            print(f"[ERROR] Failed building {app_name}: {e}")

    save_json(PUBLISHED_FILE, published)
    rebuild_portal_sitemap_and_rss(published, mon_cfg)
    if new_urls and SITE_BASE_URL:
        new_urls.append(f"{SITE_BASE_URL}/")
        notify_search_engines(new_urls)
    print(f"[DONE] Published {count} new appliance wattage calculator pages.")


if __name__ == "__main__":
    main()
