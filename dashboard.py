from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from functools import lru_cache
from html import escape
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st


ROOT = Path(__file__).parent
TEAM_NAME = os.getenv("TEAM_NAME", "QueueSense")
REFERENCE_YEARS = [2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025]
PARKS = ["Magic Kingdom", "Epcot", "Hollywood Studios", "Animal Kingdom"]
PARK_API_IDS = {"Magic Kingdom": 6, "Epcot": 5, "Hollywood Studios": 7, "Animal Kingdom": 8}
PARK_SHORT = {"Magic Kingdom": "MK", "Epcot": "EP", "Hollywood Studios": "HS", "Animal Kingdom": "AK"}
PARK_COLORS = {"Magic Kingdom": "#FF5E7E", "Epcot": "#4C86F7", "Hollywood Studios": "#F4B942", "Animal Kingdom": "#45A878"}
PARK_ICONS = {"Magic Kingdom": "🏰", "Epcot": "🌐", "Hollywood Studios": "🎬", "Animal Kingdom": "🌳"}
STEP_THEMES = {
    1: {
        "image": "app/static/backgrounds/trip-brief.jpg",
        "position": "center center",
        "credit": "Michael Gray · CC BY-SA 2.0",
        "page": "https://commons.wikimedia.org/wiki/File:Magic_Kingdom_-_Cinderella_Castle_panorama_-_by_mrkathika.jpg",
    },
    2: {
        "image": "app/static/backgrounds/travel-plan.jpg",
        "position": "center center",
        "credit": "Jedi94 · CC BY-SA 4.0",
        "page": "https://commons.wikimedia.org/wiki/File:Tree_of_Life,_Disney%27s_Animal_Kingdom.jpg",
    },
    3: {
        "image": "app/static/backgrounds/route-review.jpg",
        "position": "center center",
        "credit": "traveljunction · CC BY-SA 2.0",
        "page": "https://commons.wikimedia.org/wiki/File:The_colourful_parade_at_Walt_Disney_World_Resort_in_Orlando,_Florida_with_Snow_White_%26_the_Seven_Dwarfs_(15631604701).jpg",
    },
    4: {
        "image": "app/static/backgrounds/saved.jpg",
        "position": "center center",
        "credit": "Dancorona21 · CC BY-SA 4.0",
        "page": "https://commons.wikimedia.org/wiki/File:Cinderella%27s_Castle_at_Night.jpg",
    },
}
INK, MUTED, TEAL, CORAL, GOLD = "#19183B", "#65647D", "#5B4AE6", "#FF5E7E", "#F4C95D"
HIGH_INDEX = 1.10
LIVE_CACHE_SECONDS = 300
LIVE_STALE_MINUTES = 15
TRIP_PRESSURE_HELP = (
    "Mean of the selected visits' comparable-date historical indices. Each visit is measured "
    "against its own park and year: 1.00× is that park-year average. Indices do not compare "
    "actual wait minutes between parks, and a lower route index is not the same percentage "
    "reduction in queue time."
)
HIGH_PRESSURE_HELP = (
    "Visits at or above the manager's 1.10× review threshold. This is a human-review rule, "
    "not a validated prediction boundary."
)
MUST_DO_HELP = (
    "Selected must-do attractions whose park appears in the route. This park-level check does "
    "not guarantee completion or validate queues, travel time, operating hours, or closures."
)
PERSISTED_INPUT_KEYS = (
    "trip_start",
    "trip_days",
    "considered_parks",
    "must_rides",
    "pace",
    "ticket",
    "hotel",
    "early_entry",
    "customise_route",
)


def inject_styles(step: int) -> None:
    theme = STEP_THEMES.get(step, STEP_THEMES[1])
    review_css = """
.brandbar{min-height:58px;padding:.48rem .9rem;border-radius:16px}
.brandbar h1{font-size:clamp(1.45rem,1.35vw,2rem)}
.brandbar p{display:none}
.stepper{gap:.36rem;margin:0}
.step{padding:.28rem .5rem}
.data-ribbon{padding:.32rem .65rem}
.st-key-guided_workspace{min-height:0;padding:.64rem .82rem;background:rgba(250,248,244,.94);border-color:rgba(255,255,255,.88);backdrop-filter:blur(8px)}
.st-key-guided_workspace>div[data-testid="stVerticalBlock"]{gap:.38rem}
.work-head{padding:.42rem .62rem;margin:0;background:rgba(255,255,255,.97);border-color:rgba(69,53,120,.13)}
.work-head h2{font-size:clamp(1.35rem,1.16vw,1.8rem)}
.work-head p{font-size:.78rem}
.st-key-guided_workspace div[data-testid="stVerticalBlockBorderWrapper"]{background:rgba(255,255,255,.97);backdrop-filter:none}
.st-key-guided_workspace [data-testid="stMetric"]{min-height:78px;background:rgba(255,255,255,.99)!important;border-color:rgba(62,49,112,.16)!important}
.st-key-guided_workspace [data-testid="stMetricLabel"]{font-size:.72rem}
.st-key-guided_workspace [data-testid="stMetricValue"]{font-size:1.42rem}
.st-key-guided_workspace [data-testid="stCaptionContainer"]{display:block;padding:.44rem .58rem;background:rgba(255,255,255,.98);font-size:.74rem;line-height:1.45}
.st-key-guided_workspace [data-testid="stImage"]{padding:.42rem .5rem;border:1px solid rgba(62,49,112,.13);border-radius:14px;background:#FFFEFC}
.decision-main,.decision-score,.swap,.manager-action{box-shadow:0 4px 14px rgba(25,24,59,.055)}
.decision-main b{font-size:.83rem}.decision-main p{font-size:.74rem;line-height:1.5}
.decision-score span{font-size:.66rem}.decision-score strong{font-size:1.42rem}
.swap{padding:.48rem .56rem;font-size:.75rem;background:rgba(255,255,255,.99)}
.manager-action{padding:.68rem .72rem;background:rgba(255,247,224,.98);font-size:.75rem;line-height:1.5}
""" if step == 2 else ""
    st.markdown(
        f"""
<style>
:root{{--ink:{INK};--muted:{MUTED};--teal:{TEAL};--coral:{CORAL};--gold:{GOLD};--line:rgba(16,52,58,.13);--glass:rgba(255,252,245,.80)}}
html{{font-size:17px}}
html,body,[class*="css"]{{font-family:"Aptos","Segoe UI Variable Text","Segoe UI",sans-serif;color:var(--ink)}}
[data-testid="stAppViewContainer"]{{position:relative;background:#171633;overflow-x:hidden;overflow-y:auto}}
[data-testid="stAppViewContainer"]::before{{content:"";position:fixed;inset:0;z-index:0;background-color:#171633;background-image:linear-gradient(110deg,rgba(14,16,57,.48) 0%,rgba(61,44,129,.22) 43%,rgba(255,94,126,.07) 72%,rgba(246,202,94,.07) 100%),url("{theme['image']}");background-position:center,{theme['position']};background-size:cover,cover;background-repeat:no-repeat}}
[data-testid="stAppViewContainer"]::after{{content:"✦";position:fixed;inset:0;z-index:0;padding:4vh 4vw;color:rgba(255,224,132,.66);font-size:1.05rem;letter-spacing:28vw;text-shadow:18vw 8vh 0 rgba(255,255,255,.42),42vw 20vh 0 rgba(255,205,111,.52),68vw 5vh 0 rgba(255,255,255,.46),78vw 45vh 0 rgba(255,118,164,.42),8vw 72vh 0 rgba(255,255,255,.40);background:radial-gradient(circle at 12% 9%,rgba(255,207,102,.20),transparent 22%),linear-gradient(180deg,rgba(29,25,86,.04),rgba(255,104,151,.08));pointer-events:none}}
[data-testid="stHeader"],[data-testid="stToolbar"],footer{{display:none!important}}
[data-testid="stMain"]{{position:relative;z-index:1}}
[data-testid="stMainBlockContainer"]{{width:96vw;max-width:none;min-height:100svh;height:auto;overflow:visible;padding:.65rem 0 1.2rem;margin:0 auto}}
[data-testid="stMainBlockContainer"]>div>div[data-testid="stVerticalBlock"]{{gap:.48rem}}
.brandbar{{position:relative;display:grid;grid-template-columns:1fr auto;gap:1rem;align-items:center;min-height:76px;padding:.68rem 1.15rem;border:1px solid rgba(255,255,255,.55);border-radius:20px;background:linear-gradient(115deg,rgba(21,23,72,.91),rgba(82,55,167,.84) 62%,rgba(209,61,120,.78));backdrop-filter:blur(3px);box-shadow:0 20px 56px rgba(20,13,61,.28)}}
.brand-kicker{{color:#FFD78C;font-size:clamp(.66rem,.36vw + .26rem,.86rem);font-weight:850;letter-spacing:.15em;text-transform:uppercase}}.brandbar h1{{margin:.16rem 0 0;color:white;font:500 clamp(1.72rem,1.55vw,2.55rem)/1 Georgia,"Times New Roman",serif;letter-spacing:-.035em}}.brandbar p{{margin:.22rem 0 0;color:rgba(255,255,255,.78);font-size:clamp(.74rem,.38vw + .28rem,.94rem)}}
.brand-magic{{position:absolute;right:15.4rem;top:.48rem;color:rgba(255,224,142,.86);font-size:.9rem;letter-spacing:.22rem;filter:drop-shadow(0 2px 6px rgba(20,13,61,.34));pointer-events:none}}
.live-chip{{display:flex;align-items:center;gap:.68rem;max-width:510px;padding:.62rem .78rem;border:1px solid rgba(255,255,255,.20);border-radius:14px;background:rgba(255,255,255,.10);color:white}}.live-chip i{{flex:0 0 auto;width:10px;height:10px;border-radius:50%;background:#75D6A8;box-shadow:0 0 0 6px rgba(117,214,168,.14)}}.live-chip.partial i,.live-chip.stale i,.live-chip.inactive i{{background:#F4C95D;box-shadow:0 0 0 6px rgba(244,201,93,.15)}}.live-chip.unavailable i{{background:#FF7792;box-shadow:0 0 0 6px rgba(255,119,146,.15)}}.live-chip b{{display:block;font-size:.78rem}}.live-chip small{{display:block;color:rgba(255,255,255,.72);font-size:.64rem;line-height:1.35;margin-top:.12rem}}
.stepper{{display:grid;grid-template-columns:repeat(4,1fr);gap:.5rem;margin:.05rem 0}}
.step{{display:flex;align-items:center;gap:.56rem;padding:.38rem .62rem;border:1px solid rgba(255,255,255,.54);border-radius:12px;background:rgba(250,248,255,.76);backdrop-filter:blur(16px);color:var(--muted)}}.step.active{{background:linear-gradient(110deg,rgba(45,38,112,.96),rgba(112,62,177,.94));color:white}}.step.done{{background:rgba(241,232,255,.92);color:#5A3E9B}}.step-num{{display:grid;place-items:center;width:25px;height:25px;border-radius:50%;background:rgba(255,255,255,.84);color:var(--ink);font-size:.66rem;font-weight:900}}.step b{{display:block;font-size:.72rem}}.step small{{display:block;font-size:.62rem;opacity:.76;margin-top:.04rem}}
.data-ribbon{{display:flex;flex-wrap:wrap;gap:.38rem .8rem;align-items:center;padding:.42rem .72rem;border:1px solid rgba(255,255,255,.5);border-radius:12px;background:rgba(27,23,75,.74);color:rgba(255,255,255,.88);backdrop-filter:blur(3px);font-size:.66rem;font-weight:700}}.data-ribbon span{{white-space:nowrap}}.data-ribbon b{{color:#FFE197}}
.st-key-guided_workspace{{min-height:calc(100svh - 151px);height:auto;padding:.78rem 1rem;border:1px solid rgba(255,255,255,.68);border-radius:20px;background:linear-gradient(110deg,rgba(255,250,241,.30) 0%,rgba(255,250,241,.14) 58%,rgba(255,250,241,.06) 100%);box-shadow:0 24px 70px rgba(10,45,50,.22);overflow:visible}}
.st-key-guided_workspace>div[data-testid="stVerticalBlock"]{{gap:.55rem}}
.st-key-guided_workspace div[data-testid="stVerticalBlock"]{{gap:.42rem}}
.work-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:1rem;margin:0 0 .25rem;padding:.55rem .7rem;border:1px solid rgba(255,255,255,.46);border-radius:14px;background:rgba(253,249,255,.70);backdrop-filter:blur(2px)}}.work-head h2{{margin:0;font:500 clamp(1.55rem,1.3vw,2.1rem)/1.08 Georgia,"Times New Roman",serif;letter-spacing:-.025em}}.work-head p{{margin:.13rem 0 0;color:var(--muted);font-size:.82rem}}.work-tag{{padding:.3rem .55rem;border-radius:99px;background:#EEE7FF;color:#5B3EA6;font-size:.68rem;font-weight:850;white-space:nowrap}}
div[data-testid="stVerticalBlockBorderWrapper"]{{border-color:rgba(16,52,58,.18)!important;border-radius:16px!important;background:rgba(255,255,255,.65);box-shadow:0 7px 21px rgba(20,52,59,.07);backdrop-filter:blur(3px)}}
label[data-testid="stWidgetLabel"] p{{font-size:.82rem!important;font-weight:780!important;color:var(--ink)!important}}
div[data-baseweb="select"]>div,div[data-testid="stDateInput"] input{{min-height:40px!important;border-color:rgba(20,52,59,.16)!important;border-radius:10px!important;background:rgba(255,253,248,.94)!important}}
.st-key-guided_workspace [data-testid="stCheckbox"]{{width:max-content;max-width:100%;padding:.42rem .62rem;border:1px solid rgba(255,255,255,.42);border-radius:11px;background:rgba(255,250,241,.70);backdrop-filter:blur(2px)}}
.st-key-guided_workspace [data-testid="stCaptionContainer"]{{display:inline-block;padding:.34rem .52rem;border-radius:9px;background:rgba(255,250,241,.72);backdrop-filter:blur(2px)}}
.stButton button{{min-height:42px;border-radius:11px;border:1px solid rgba(20,52,59,.15);font-size:.82rem;font-weight:800}}
[data-testid="stBaseButton-primary"]{{background:linear-gradient(110deg,#4B3CC4,#8C4BC4 60%,#DD4F87)!important;color:white!important;border-color:rgba(255,255,255,.26)!important;box-shadow:0 8px 20px rgba(55,36,136,.24)!important}}
.route-summary-stack{{display:grid;grid-template-rows:auto auto auto;gap:.72rem;align-content:start;width:100%;min-width:0;isolation:isolate;contain:layout style}}.route-summary-stack>*{{position:relative;min-width:0;margin:0!important}}
.brief-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.65rem;margin:0}}.brief-card{{min-width:0;min-height:92px;padding:.78rem .82rem;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.70);backdrop-filter:blur(2px);overflow-wrap:anywhere}}.brief-card h3{{margin:0 0 .28rem;font:500 1.18rem/1.1 Georgia,"Times New Roman",serif}}.brief-card p{{margin:0;color:var(--muted);font-size:.76rem;line-height:1.42}}
.recommend-preview{{position:relative;z-index:1;width:100%;min-width:0;height:auto;margin-bottom:.14rem;padding:.88rem .95rem 1rem;border-radius:16px;background:linear-gradient(135deg,rgba(31,29,91,.97),rgba(91,61,181,.94) 60%,rgba(190,64,137,.90));color:white;overflow:hidden;contain:layout paint}}.recommend-preview h3{{margin:0;color:white;font:500 1.28rem/1.1 Georgia,"Times New Roman",serif}}.recommend-preview p{{margin:.25rem 0 .68rem;color:rgba(255,255,255,.76);font-size:.7rem}}.preview-route{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.45rem;width:100%;min-width:0}}.preview-day{{min-width:0;padding:.52rem .55rem;border-radius:10px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.18)}}.preview-day small{{display:block;color:#FFE197;font-size:.57rem;font-weight:850}}.preview-day b{{display:block;margin:.15rem 0;font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.preview-day span{{font-size:.58rem;color:rgba(255,255,255,.72)}}
.st-key-opening_kpis{{position:relative;z-index:1;margin:.72rem 0 .55rem}}.st-key-preview_action{{position:relative;z-index:1;margin-top:.72rem}}
.day-card{{height:100%;padding:.55rem .58rem;border-top:4px solid var(--park);border-radius:13px;background:rgba(255,255,255,.74);box-shadow:0 7px 18px rgba(18,52,58,.05)}}.day-card small{{display:block;color:var(--muted);font-size:.55rem;font-weight:750}}.day-card h3{{margin:.16rem 0;font:500 .95rem/1.06 Georgia,"Times New Roman",serif}}.day-card .index{{font:500 1.3rem/1 Georgia,"Times New Roman",serif}}.day-card .index span{{font:.58rem "Aptos","Segoe UI",sans-serif;color:var(--muted)}}.day-card p{{margin:.25rem 0 0;color:var(--muted);font-size:.57rem;line-height:1.35}}
.decision-bar{{display:grid;grid-template-columns:1.25fr .75fr;gap:.6rem;margin:.45rem 0}}.decision-main{{padding:.6rem .68rem;border-left:4px solid var(--tone);border-radius:0 12px 12px 0;background:var(--decision-bg)}}.decision-main b{{font-size:.75rem}}.decision-main p{{margin:.13rem 0 0;color:#53666A;font-size:.64rem;line-height:1.4}}.decision-score{{display:flex;align-items:center;justify-content:space-around;padding:.48rem;border-radius:12px;background:rgba(255,255,255,.70);border:1px solid var(--line)}}.decision-score div{{text-align:center}}.decision-score strong{{display:block;font:500 1.3rem Georgia,"Times New Roman",serif}}.decision-score span{{font-size:.56rem;color:var(--muted)}}
.opening-status{{margin:.05rem 0 .12rem;padding:.66rem .72rem;border-left:4px solid var(--tone);border-radius:0 12px 12px 0;background:var(--decision-bg);box-shadow:0 7px 18px rgba(18,52,58,.05)}}.opening-status b{{display:block;font-size:.76rem}}.opening-status p{{margin:.16rem 0 0;color:#53666A;font-size:.65rem;line-height:1.42}}
.manager-action{{margin-top:.48rem;padding:.58rem .64rem;border-radius:11px;background:rgba(255,241,209,.88);border:1px solid rgba(174,118,24,.18);color:#624615;font-size:.66rem;line-height:1.45}}.manager-action b{{color:var(--ink)}}
.route-rationale-panel{{display:grid;grid-template-rows:auto;align-content:start;gap:.55rem;width:100%;min-width:0;isolation:isolate;contain:layout style}}.route-rationale-panel>*{{position:relative;min-width:0;margin:0!important}}
.swap-list{{display:grid;gap:.32rem;width:100%;min-width:0}}.swap{{display:grid;grid-template-columns:66px minmax(0,1fr) auto;gap:.45rem;align-items:center;min-width:0;padding:.42rem .5rem;border-radius:9px;background:rgba(255,255,255,.76);border:1px solid rgba(72,50,142,.12);font-size:.68rem}}.swap b{{color:var(--coral)}}.swap span{{min-width:0;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.swap em{{font-style:normal;color:#5341C8;font-weight:850}}
.priority{{padding:.4rem .46rem;border-radius:9px;background:rgba(255,255,255,.69);border:1px solid rgba(20,52,59,.08)}}.priority b{{display:block;font-size:.62rem}}.priority span{{display:block;margin-top:.08rem;color:var(--muted);font-size:.56rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
[data-testid="stMetric"]{{min-height:70px;padding:.42rem .56rem!important;border:1px solid var(--line)!important;border-radius:12px!important;background:rgba(255,255,255,.76)}}[data-testid="stMetricLabel"]{{color:var(--muted);font-size:.60rem}}[data-testid="stMetricValue"]{{font:500 1.25rem Georgia,"Times New Roman",serif;color:var(--ink)}}
.final-banner{{display:grid;grid-template-columns:1fr auto;gap:1rem;align-items:end;padding:.9rem 1rem;border-radius:16px;background:linear-gradient(120deg,rgba(28,27,89,.97),rgba(93,58,178,.92) 62%,rgba(202,62,132,.88));color:white}}.final-banner h2{{margin:0;color:white;font:500 1.65rem Georgia,"Times New Roman",serif}}.final-banner p{{margin:.22rem 0 0;color:rgba(255,255,255,.76);font-size:.72rem}}.final-badge{{padding:.42rem .6rem;border-radius:10px;background:rgba(255,255,255,.14);font-size:.62rem;color:#FFE197;font-weight:850}}
.final-day{{padding:.7rem .72rem;border-radius:13px;background:rgba(255,255,255,.72);backdrop-filter:blur(2px);border:1px solid var(--line);border-top:4px solid var(--park)}}.final-day small{{font-size:.64rem;color:var(--muted)}}.final-day h3{{margin:.16rem 0 .3rem;font:500 1.06rem Georgia,"Times New Roman",serif}}.final-day p{{margin:.11rem 0;color:var(--muted);font-size:.69rem;line-height:1.4}}.final-day b{{color:var(--ink)}}
.trip-checks{{display:grid;grid-template-columns:1.35fr .65fr;gap:.58rem;margin:.08rem 0}}.trip-check{{min-width:0;padding:.62rem .72rem;border:1px solid rgba(255,255,255,.56);border-radius:12px;background:rgba(255,255,255,.72);backdrop-filter:blur(3px)}}.trip-check b{{display:block;margin-bottom:.15rem;color:#5141BE;font-size:.68rem;letter-spacing:.025em;text-transform:uppercase}}.trip-check p{{margin:0;color:#52516A;font-size:.7rem;line-height:1.45}}
.success-shell{{min-height:calc(100svh - 270px);display:grid;place-items:center;text-align:center;padding:1.4rem}}.success-card{{width:min(820px,92vw);padding:clamp(2rem,5vw,4.5rem);border:1px solid rgba(255,255,255,.74);border-radius:30px;background:linear-gradient(145deg,rgba(255,251,255,.84),rgba(236,228,255,.70));box-shadow:0 30px 80px rgba(30,17,81,.28);backdrop-filter:blur(3px)}}.success-icon{{display:grid;place-items:center;width:82px;height:82px;margin:0 auto 1rem;border-radius:50%;background:linear-gradient(145deg,#4B3CC4,#C54891);color:white;font-size:2.25rem;box-shadow:0 14px 34px rgba(76,50,190,.32)}}.success-card h2{{margin:.2rem 0;font:500 clamp(2rem,3vw,3rem)/1.05 Georgia,"Times New Roman",serif;color:var(--ink)}}.success-card .celebrate{{margin:.7rem auto 1rem;font-size:1.12rem;color:#7B4A17;font-weight:800}}.success-card p{{max-width:650px;margin:.45rem auto;color:var(--muted);font-size:.96rem;line-height:1.65}}.success-chips{{display:flex;flex-wrap:wrap;justify-content:center;gap:.5rem;margin:1.25rem 0 .4rem}}.success-chips span{{padding:.46rem .72rem;border-radius:99px;background:rgba(255,255,255,.80);border:1px solid var(--line);font-size:.78rem;font-weight:800}}.st-key-success_actions [data-testid="stHorizontalBlock"]{{align-items:stretch!important}}.st-key-success_actions [data-testid="stColumn"]{{display:flex!important;align-items:stretch!important}}.st-key-success_actions [data-testid="stColumn"]>div{{width:100%!important;display:flex!important}}.st-key-success_actions [data-testid="stButton"]{{width:100%!important;display:flex!important}}.st-key-success_actions button{{width:100%!important;height:100%!important;min-height:46px!important}}
.full-screen-celebration{{position:fixed;inset:0;overflow:hidden;pointer-events:none}}.balloon-intro{{z-index:8}}.balloon-intro .color-balloon{{position:absolute;left:var(--x);bottom:var(--start);width:var(--size);aspect-ratio:.78;border-radius:52% 52% 48% 48%;background:radial-gradient(circle at 30% 24%,rgba(255,255,255,.92) 0 7%,rgba(255,255,255,.28) 8% 15%,transparent 16%),linear-gradient(145deg,rgba(255,255,255,.20),var(--color) 48%,color-mix(in srgb,var(--color),#2C235E 28%));box-shadow:inset -7px -9px 14px rgba(43,25,92,.16),0 8px 18px rgba(29,20,79,.18);filter:saturate(1.08);opacity:0;animation:balloon-rise var(--duration) linear var(--delay) both}}.balloon-intro .color-balloon::before{{content:"";position:absolute;left:50%;bottom:-5px;transform:translateX(-50%);width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-top:8px solid var(--color)}}.balloon-intro .color-balloon::after{{content:"";position:absolute;left:50%;top:calc(100% + 3px);width:1px;height:38px;background:linear-gradient(rgba(255,255,255,.82),rgba(255,255,255,.08));transform:translateX(-50%) rotate(var(--string-tilt));transform-origin:top}}.ambient-celebration{{z-index:6}}.ambient-celebration span{{position:absolute;left:var(--x);bottom:-14vh;font-size:clamp(1.2rem,2.2vw,2.2rem);filter:drop-shadow(0 5px 10px rgba(30,17,81,.22));animation:float-celebration var(--duration) linear var(--delay) infinite}}@keyframes balloon-rise{{0%{{transform:translate3d(0,0,0) rotate(-4deg);opacity:.96}}94%{{opacity:.96}}100%{{transform:translate3d(var(--drift),-150vh,0) rotate(5deg);opacity:0}}}}@keyframes float-celebration{{0%{{transform:translate3d(0,0,0) rotate(-5deg);opacity:0}}10%{{opacity:.92}}88%{{opacity:.86}}100%{{transform:translate3d(var(--drift),-120vh,0) rotate(16deg);opacity:0}}}}
.source-foot{{position:relative;margin:.28rem 1rem 0;text-align:right;color:rgba(255,255,255,.88);font-size:.60rem;z-index:3;text-shadow:0 1px 5px rgba(0,0,0,.48)}}.source-foot a{{color:inherit}}
{review_css}
@media(max-width:1100px){{.brief-grid{{grid-template-columns:1fr}}.brief-card{{min-height:0}}.work-head{{align-items:flex-start}}}}
@media(max-width:900px){{html{{font-size:16.5px}}[data-testid="stAppViewContainer"]{{overflow:visible}}[data-testid="stAppViewContainer"]::before{{background-image:linear-gradient(180deg,rgba(23,19,73,.42),rgba(109,47,139,.14),rgba(255,107,148,.08)),url("{theme['image']}");background-position:center,{theme['position']};background-size:cover,cover}}[data-testid="stMainBlockContainer"]{{width:auto;height:auto;overflow:visible;padding:.6rem .55rem 2rem}}.brandbar{{grid-template-columns:1fr;padding:.78rem .9rem}}.brandbar h1{{font-size:1.55rem}}.brand-magic,.live-chip{{display:none}}.data-ribbon{{font-size:.68rem;gap:.3rem .6rem}}.data-ribbon span{{white-space:normal}}.stepper{{grid-template-columns:repeat(2,1fr)}}.step small{{display:none}}.st-key-guided_workspace{{height:auto;min-height:0;overflow:visible;padding:.75rem;background:rgba(249,243,255,.30)}}.st-key-guided_workspace [data-testid="stVerticalBlock"],.st-key-guided_workspace [data-testid="stColumn"],.st-key-guided_workspace [data-testid="stLayoutWrapper"]{{height:auto!important;max-height:none!important;overflow:visible!important}}.work-head{{display:block;background:rgba(253,249,255,.75)}}.work-tag{{display:inline-block;margin-top:.45rem}}.decision-bar{{grid-template-columns:1fr}}.preview-route{{grid-template-columns:repeat(2,minmax(0,1fr))}}.brief-grid{{grid-template-columns:1fr}}.final-banner{{grid-template-columns:minmax(0,1fr);align-items:start}}.final-banner h2{{font-size:1.45rem;overflow-wrap:normal}}.final-badge{{justify-self:start}}.trip-checks{{grid-template-columns:1fr}}.source-foot{{display:none}}.success-shell{{padding:1rem .15rem;min-height:68vh}}}}
@media(prefers-reduced-motion:reduce){{.full-screen-celebration{{display:none}}}}
</style>
""",
        unsafe_allow_html=True,
    )


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    calendar = pd.read_csv(ROOT / "data" / "calendar_enriched.csv", parse_dates=["date"])
    reference = calendar.loc[calendar["year"].isin(REFERENCE_YEARS)].copy()
    rides = pd.read_csv(ROOT / "data" / "ride_stats.csv")
    active = rides.loc[(rides["year"].astype(str) == "all_time") & (rides["metric"] == "ride_avg_wait") & (rides["is_archived"] == 0)].copy()
    pass_classes = pd.read_csv(ROOT / "data" / "ll_classification.csv")
    active = active.merge(pass_classes[["park_id", "ride_id", "ll_class"]], on=["park_id", "ride_id"], how="left")
    active["option"] = active["ride_name"] + "  ·  " + active["park_name"]
    return reference, active.sort_values(["park_name", "minutes"], ascending=[True, False])


def _fetch_park(park: str, park_id: int) -> list[dict[str, object]]:
    request = Request(f"https://queue-times.com/en-US/parks/{park_id}/queue_times.json", headers={"User-Agent": "QueueSense classroom dashboard/1.0"})
    with urlopen(request, timeout=5) as response:
        payload = json.load(response)
    rows: list[dict[str, object]] = []
    for land in payload.get("lands", []):
        for ride in land.get("rides", []):
            raw_wait = ride.get("wait_time")
            try:
                wait_minutes = float(raw_wait) if raw_wait is not None else np.nan
            except (TypeError, ValueError):
                wait_minutes = np.nan
            rows.append(
                {
                    "park": park,
                    "ride": ride.get("name", "Unknown"),
                    "is_open": bool(ride.get("is_open", False)),
                    "wait_minutes": wait_minutes,
                    "updated": ride.get("last_updated"),
                }
            )
    return rows


@st.cache_data(ttl=LIVE_CACHE_SECONDS, show_spinner=False)
def fetch_live() -> pd.DataFrame:
    if os.getenv("QUEUESENSE_SKIP_LIVE") == "1":
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        jobs = {executor.submit(_fetch_park, park, park_id): park for park, park_id in PARK_API_IDS.items()}
        for job in as_completed(jobs):
            try:
                rows.extend(job.result())
            except (HTTPError, URLError, TimeoutError, OSError, ValueError):
                continue
    if not rows:
        return pd.DataFrame()
    live = pd.DataFrame(rows)
    live["updated"] = pd.to_datetime(live["updated"], utc=True, errors="coerce")
    return live


def summarise_live_snapshot(live: pd.DataFrame, now: pd.Timestamp | None = None) -> dict[str, str]:
    """Summarise source coverage and freshness without treating missing waits as zero."""
    if live.empty:
        return {
            "status": "unavailable",
            "title": "Live signal unavailable",
            "note": "Historical planning remains available · retry on interaction or reload",
        }

    covered_parks = [park for park in PARKS if park in set(live["park"].dropna())]
    open_now = live.loc[live["is_open"].fillna(False)].copy()
    reported_waits = pd.to_numeric(open_now["wait_minutes"], errors="coerce").dropna()
    latest = pd.to_datetime(live["updated"], utc=True, errors="coerce").max()
    now_utc = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if now_utc.tzinfo is None:
        now_utc = now_utc.tz_localize("UTC")
    else:
        now_utc = now_utc.tz_convert("UTC")
    is_stale = pd.notna(latest) and (now_utc - latest) > pd.Timedelta(minutes=LIVE_STALE_MINUTES)
    is_partial = len(covered_parks) < len(PARKS)

    if open_now.empty:
        title = f"No open attractions reported · {len(covered_parks)}/4 parks"
    elif reported_waits.empty:
        title = f"{len(open_now)} open attractions · waits unavailable"
    else:
        title = f"{len(open_now)} open · {reported_waits.median():.0f} min median"

    coverage = f"{len(covered_parks)}/4 parks"
    denominator = f"{len(reported_waits)}/{len(open_now)} open attractions with reported waits"
    if pd.notna(latest):
        source_time = latest.tz_convert("America/New_York").strftime("%b %d, %Y · %I:%M %p ET")
    else:
        source_time = "source time unavailable"
    note = f"{coverage} · {denominator} · updated {source_time}"

    qualifiers: list[str] = []
    if is_stale:
        qualifiers.append(f"Stale (>{LIVE_STALE_MINUTES} min)")
    if is_partial:
        qualifiers.append("Partial coverage")
    if pd.isna(latest):
        qualifiers.append("Source time unavailable")
    if open_now.empty:
        qualifiers.insert(0, "No open attractions in returned scope")
    if qualifiers:
        note = f"{' · '.join(qualifiers)} · {note}"

    if open_now.empty:
        status = "inactive"
    elif is_stale:
        status = "stale"
    elif is_partial or pd.isna(latest):
        status = "partial"
    else:
        status = "fresh"
    return {"status": status, "title": title, "note": note}


def estimate(reference: pd.DataFrame, planned_date: pd.Timestamp, park: str) -> dict[str, object]:
    comparable = reference.loc[(reference["park_name"] == park) & (reference["month"] == planned_date.month) & (reference["day_of_week"] == planned_date.day_name())]
    values = comparable["crowd_rel_to_year"].dropna()
    return {"date": planned_date, "park": park, "index": float(values.median()), "q25": float(values.quantile(.25)), "q75": float(values.quantile(.75)), "sample": int(len(values))}


def route_frame(reference: pd.DataFrame, route: list[tuple[int, pd.Timestamp, str]]) -> pd.DataFrame:
    records = []
    for day_number, when, park in route:
        item = estimate(reference, when, park)
        item["day"] = day_number
        records.append(item)
    return pd.DataFrame(records)


def must_do_coverage(
    route_df: pd.DataFrame,
    must_options: list[str],
    ride_lookup: dict[str, dict[str, object]],
) -> tuple[int, str]:
    """Return covered must-do count and the shared dashboard label."""
    selected_parks = set(route_df["park"])
    covered = sum(1 for item in must_options if ride_lookup[item]["park_name"] in selected_parks)
    label = f"{covered} / {len(must_options)}" if must_options else "None selected"
    return covered, label


def has_duplicate_hopper_parks(route: list[tuple[int, pd.Timestamp, str]]) -> bool:
    """Return whether any route day assigns the same park more than once."""
    if not route:
        return False
    route_rows = pd.DataFrame(route, columns=["day", "date", "park"])
    return any(
        len(parks) != len(set(parks))
        for parks in route_rows.groupby("day")["park"].agg(list)
    )


def decision_message(
    selected_df: pd.DataFrame,
    missing_must_dos: bool,
    average_change: float = 0.0,
    customised: bool = False,
) -> tuple[str, str, str, str]:
    """Create one evidence-based status used by both decision screens."""
    flagged = selected_df.loc[selected_df["index"] >= HIGH_INDEX].sort_values("index", ascending=False)
    if missing_must_dos:
        return (
            CORAL,
            "#FFE7EF",
            "Must-do coverage needs attention.",
            "Restore a park containing every selected must-do before creating the visitor travel plan.",
        )
    if not flagged.empty:
        flagged_text = "; ".join(
            f"Day {int(row.day)} {row.park} ({row.index:.2f}×)" for row in flagged.itertuples()
        )
        change_note = (
            f" The custom route is {average_change:.1%} above the system draft."
            if customised and average_change > .03
            else ""
        )
        return (
            CORAL,
            "#FFF0E5",
            f"Review required — {len(flagged)} of {len(selected_df)} visits meet the 1.10× threshold.",
            f"Flagged: {flagged_text}. Review park order or prepare a lower-pressure backup; this is a historical planning signal, not a forecast.{change_note}",
        )
    if customised and average_change > .03:
        return (
            GOLD,
            "#FFF4D7",
            "The custom route adds measurable historical pressure.",
            f"Its index is {average_change:.1%} above the system proposal. Keep the change only when visitor preference or access outweighs the historical difference.",
        )
    return (
        TEAL,
        "#EEE9FF",
        "No route visit reaches the historical review threshold.",
        "Must-do coverage and ticket constraints are protected. The itinerary manager can continue to the detailed review.",
    )


def build_slots(planned_dates: list[pd.Timestamp], required_count: int, ticket: str) -> list[tuple[int, pd.Timestamp]]:
    slots = [(index + 1, when) for index, when in enumerate(planned_dates)]
    extra_needed = max(0, required_count - len(planned_dates)) if ticket == "Park Hopper" else 0
    for index in range(min(extra_needed, len(planned_dates))):
        slots.append((index + 1, planned_dates[index]))
    return sorted(slots, key=lambda item: item[0])


def propose_route(
    reference: pd.DataFrame,
    planned_dates: list[pd.Timestamp],
    parks: list[str],
    required: set[str],
    ticket: str,
) -> list[tuple[int, pd.Timestamp, str]] | None:
    capacity = len(planned_dates) * (2 if ticket == "Park Hopper" else 1)
    if not parks or len(required) > capacity:
        return None
    slots = build_slots(planned_dates, len(required), ticket)
    target_unique = min(len(parks), max(len(required), min(len(planned_dates), len(parks))))
    park_bits = {park: 1 << index for index, park in enumerate(parks)}
    required_mask = sum(park_bits[park] for park in required if park in park_bits)
    scores = {(index, park): float(estimate(reference, when, park)["index"]) for index, (_, when) in enumerate(slots) for park in parks}

    @lru_cache(maxsize=None)
    def solve(index: int, covered: int, previous: str) -> tuple[float, float, tuple[str, ...]] | None:
        if index == len(slots):
            enough_variety = covered.bit_count() >= target_unique
            required_covered = covered & required_mask == required_mask
            return (0.0, 0.0, ()) if enough_variety and required_covered else None
        same_day = index > 0 and slots[index - 1][0] == slots[index][0]
        best = None
        for park in parks:
            if same_day and park == previous:
                continue
            suffix = solve(index + 1, covered | park_bits[park], park)
            if suffix is None:
                continue
            value = scores[(index, park)]
            candidate = (value + suffix[0], max(value, suffix[1]), (park,) + suffix[2])
            if best is None or candidate[:2] < best[:2]:
                best = candidate
        return best

    result = solve(0, 0, "")
    return None if result is None else [(day, when, park) for (day, when), park in zip(slots, result[2], strict=True)]


def attraction_priorities(
    active_rides: pd.DataFrame,
    park: str,
    must_options: list[str],
    pace: str,
    excluded_names: set[str] | None = None,
    include_must: bool = True,
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    """Return every must-do plus pace-limited extras and one unique backup."""
    extra_count = {"Relaxed": 2, "Balanced": 3, "Highlights": 4}[pace]
    excluded = excluded_names or set()
    park_rides = active_rides.loc[active_rides["park_name"] == park].drop_duplicates("option").copy()
    must_set = set(must_options)
    park_rides["is_must"] = park_rides["option"].isin(must_set)
    if include_must:
        park_rides = park_rides.loc[park_rides["is_must"] | ~park_rides["ride_name"].isin(excluded)]
    else:
        park_rides = park_rides.loc[~park_rides["ride_name"].isin(excluded)]
    must_rows = (
        park_rides.loc[park_rides["is_must"]]
        .sort_values("minutes", ascending=False)
        if include_must
        else park_rides.iloc[0:0]
    )
    extra_rows = (
        park_rides.loc[
            ~park_rides["is_must"]
            & park_rides["ll_class"].ne("exclude")
        ]
        .sort_values("minutes", ascending=False)
        .head(extra_count)
    )
    selected = pd.concat([must_rows, extra_rows], ignore_index=True)
    priorities = selected[["ride_name", "minutes", "is_must", "ll_class"]].to_dict("records")
    remaining = park_rides.loc[
        ~park_rides["ride_name"].isin(selected["ride_name"])
        & ~park_rides["is_must"]
    ].sort_values("minutes")
    backup = remaining.iloc[0][["ride_name", "minutes"]].to_dict() if not remaining.empty else None
    return priorities, backup


def step_markup(current: int) -> str:
    labels = [
        ("🎠 Trip brief", "Days and must-dos"),
        ("🎢 Route review", "System proposal"),
        ("🗺️ Travel plan", "Visitor-ready brief"),
        ("🎆 Saved", "Celebrate and continue"),
    ]
    html = '<div class="stepper">'
    for index, (label, note) in enumerate(labels, start=1):
        state = "active" if index == current else "done" if index < current else ""
        marker = "✓" if index < current else str(index)
        html += f'<div class="step {state}"><span class="step-num">{marker}</span><div><b>{label}</b><small>{note}</small></div></div>'
    return html + "</div>"


def work_heading(title: str, copy: str, tag: str) -> None:
    st.markdown(f'<div class="work-head"><div><h2>{escape(title)}</h2><p>{escape(copy)}</p></div><span class="work-tag">{escape(tag)}</span></div>', unsafe_allow_html=True)


def navigate(step: int) -> None:
    st.session_state.flow_step = step
    st.session_state._scroll_to_top = True
    st.session_state._scroll_nonce = int(st.session_state.get("_scroll_nonce", 0)) + 1


def prepare_route_review(proposal: list[tuple[int, pd.Timestamp, str]]) -> None:
    st.session_state.proposed_route = proposal
    for index, (_, _, park) in enumerate(proposal):
        st.session_state[f"route_park_{index}"] = park
    navigate(2)


def accept_route(route: list[tuple[int, pd.Timestamp, str]]) -> None:
    st.session_state.accepted_route = route
    navigate(3)


def save_itinerary() -> None:
    navigate(4)


def scroll_to_top_if_needed() -> None:
    if not st.session_state.pop("_scroll_to_top", False):
        return
    scroll_script = """
        <script>
        (() => {
        const scrollResetNonce = __SCROLL_NONCE__;
        const resetScroll = () => {
          window.scrollTo(0, 0);
          const selectors = [
            '[data-testid="stAppViewContainer"]',
            '[data-testid="stMain"]',
            '[data-testid="stMainBlockContainer"]'
          ];
          selectors.forEach((selector) => {
            const element = document.querySelector(selector);
            if (element) element.scrollTop = 0;
          });
        };
        resetScroll();
        requestAnimationFrame(() => requestAnimationFrame(resetScroll));
        const resetMoments = [80, 180, 360, 650, 1050, 1600];
        resetMoments.forEach((delay) => setTimeout(resetScroll, delay));
        })();
        </script>
        """.replace("__SCROLL_NONCE__", str(int(st.session_state.get("_scroll_nonce", 0))))
    st.html(
        scroll_script,
        width="content",
        unsafe_allow_javascript=True,
    )


def route_preview_html(route: list[tuple[int, pd.Timestamp, str]], title: str, copy: str) -> str:
    by_day: dict[int, list[str]] = {}
    dates: dict[int, pd.Timestamp] = {}
    for day_number, when, park in route:
        by_day.setdefault(day_number, []).append(park)
        dates[day_number] = when
    html = f'<section class="recommend-preview"><h3>{escape(title)}</h3><p>{escape(copy)}</p><div class="preview-route">'
    for day_number in sorted(dates):
        names = " + ".join(f"{PARK_ICONS[park]} {PARK_SHORT[park]}" for park in by_day[day_number])
        html += f'<div class="preview-day"><small>DAY {day_number}</small><b>{escape(names)}</b><span>{dates[day_number].strftime("%a %b %d")}</span></div>'
    return html + "</div></section>"


def initialise_state() -> None:
    defaults = {
        "flow_step": 1,
        "trip_start": date.today() + timedelta(days=45),
        "trip_days": 4,
        "considered_parks": PARKS.copy(),
        "must_rides": [],
        "pace": "Balanced",
        "ticket": "One Park Per Day",
        "hotel": "Not decided",
        "early_entry": "Unsure",
        "customise_route": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def preserve_input_state() -> None:
    """Detach wizard inputs from Streamlit's unrendered-widget cleanup."""
    for key in PERSISTED_INPUT_KEYS:
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]


def render() -> None:
    st.set_page_config(
        page_title=f"{TEAM_NAME} | Walt Disney World Orlando Trip Design",
        page_icon="✶",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    initialise_state()
    preserve_input_state()
    current_step = int(st.session_state.flow_step)
    inject_styles(current_step)
    try:
        reference, rides = load_data()
    except (FileNotFoundError, ValueError, pd.errors.ParserError) as exc:
        st.error(f"The trip planner could not load its project data: {exc}")
        st.stop()

    live = fetch_live()
    live_summary = summarise_live_snapshot(live)

    st.markdown(
        f"""
<header class="brandbar">
  <div>
    <div class="brand-kicker">☀ CENTRAL FLORIDA · LAKE BUENA VISTA · {escape(TEAM_NAME)}</div>
    <h1>{escape(TEAM_NAME)} · Walt Disney World Orlando Trip Studio</h1>
    <p>For the itinerary product manager: review which parks to recommend and how to arrange upcoming groups using historical pressure, visitor preferences, and a live-day check.</p>
  </div>
  <div class="brand-magic" aria-hidden="true">✦ 🏰 ✦ 🎠 ✦ 🎆</div>
  <div class="live-chip {escape(live_summary['status'])}"><i></i><div><b>{escape(live_summary['title'])}</b><small>{escape(live_summary['note'])}</small></div></div>
</header>
""",
        unsafe_allow_html=True,
    )
    st.markdown(step_markup(current_step), unsafe_allow_html=True)
    st.markdown(
        '<div class="data-ribbon">'
        '<span>📅 <b>Snapshot:</b> Jan 1, 2015 – Sep 30, 2026</span>'
        '<span>🧭 <b>Planning baseline:</b> 2015–2019 &amp; 2022–2025</span>'
        '<span>📦 <b>Kaggle historical snapshot</b></span>'
        '<span>🔄 <b>Live:</b> fetched on interaction/reload · results cached 5 min</span>'
        '<span>🌙 <b>Proposed historical collection:</b> nightly · <b>Manager review:</b> Mondays</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    considered = list(st.session_state.considered_parks)
    valid_options = rides.loc[rides["park_name"].isin(considered), "option"].tolist()
    st.session_state.must_rides = [item for item in st.session_state.must_rides if item in valid_options]
    ride_lookup = rides.set_index("option")[["park_name", "ride_name", "minutes", "ll_class"]].to_dict("index")
    intro_celebration_html = ""
    ambient_celebration_html = ""

    with st.container(key="guided_workspace"):

        if current_step == 1:
            work_heading(
                "Tell us about the trip—we will propose the parks",
                "The visitor chooses dates, access, rhythm, and must-dos. The system decides the first park assignment.",
                "STEP 1 · TRIP BRIEF",
            )
            left, right = st.columns([.92, 1.35], gap="medium")
            with left:
                with st.container(border=True):
                    c1, c2 = st.columns([1.25, .75])
                    with c1:
                        st.date_input("First Disney day", key="trip_start")
                    with c2:
                        st.slider("Disney days", 1, 7, key="trip_days")
                    st.multiselect("Parks the group is willing to visit", PARKS, key="considered_parks", format_func=lambda park: f"{PARK_ICONS[park]}  {park}")
                    if not st.session_state.considered_parks:
                        st.warning("Keep at least one park available so the system can design a route.")
                        st.stop()
                    c3, c4 = st.columns(2)
                    with c3:
                        st.selectbox("Ticket access", ["One Park Per Day", "Park Hopper", "Not purchased"], key="ticket")
                    with c4:
                        st.selectbox("Trip rhythm", ["Relaxed", "Balanced", "Highlights"], key="pace")

                    considered = list(st.session_state.considered_parks)
                    valid_options = rides.loc[rides["park_name"].isin(considered), "option"].tolist()
                    st.session_state.must_rides = [item for item in st.session_state.must_rides if item in valid_options]
                    st.multiselect("Must-do attractions (optional, up to 8)", valid_options, max_selections=8, key="must_rides")
                    with st.expander("Stay & entry details (final-plan guidance only)"):
                        st.caption("These details change the final checklist, not the historical pressure score or park recommendation.")
                        c5, c6 = st.columns(2)
                        with c5:
                            st.selectbox("Hotel base", ["Disney Resort hotel", "Other Orlando hotel", "Not decided"], key="hotel")
                        with c6:
                            st.selectbox("Early-entry access", ["Yes", "No", "Unsure"], key="early_entry")

            trip_start = pd.Timestamp(st.session_state.trip_start)
            trip_days = int(st.session_state.trip_days)
            planned_dates = [trip_start + pd.Timedelta(days=offset) for offset in range(trip_days)]
            must_parks = {str(ride_lookup[item]["park_name"]) for item in st.session_state.must_rides}
            proposal = propose_route(reference, planned_dates, considered, must_parks, st.session_state.ticket)

            with right:
                if proposal is None:
                    capacity = trip_days * (2 if st.session_state.ticket == "Park Hopper" else 1)
                    st.warning(f"This ticket-and-day combination has {capacity} park slot(s), but the must-do list requires {len(must_parks)} parks. Add a day, choose Park Hopper, or reduce must-dos.")
                else:
                    preview_html = route_preview_html(
                        proposal,
                        f"Your {trip_days}-day starting route",
                        "Generated immediately from the selected dates, must-do coverage, ticket access, and comparable historical park-days.",
                    )
                    proposal_df = route_frame(reference, proposal)
                    covered_must, must_coverage_label = must_do_coverage(
                        proposal_df,
                        list(st.session_state.must_rides),
                        ride_lookup,
                    )
                    st.markdown(preview_html, unsafe_allow_html=True)
                    with st.container(key="opening_kpis"):
                        kpi_1, kpi_2, kpi_3 = st.columns(3)
                        kpi_1.metric("Historical trip pressure", f"{proposal_df['index'].mean():.2f}×", border=True, help=TRIP_PRESSURE_HELP)
                        kpi_2.metric("Higher-pressure visits", f"{int((proposal_df['index'] >= HIGH_INDEX).sum())} of {len(proposal_df)}", border=True, help=HIGH_PRESSURE_HELP)
                        kpi_3.metric("Must-dos in scheduled parks", must_coverage_label, border=True, help=MUST_DO_HELP)
                    if not st.session_state.must_rides:
                        st.info("No must-do attractions selected. The route has no attraction-based park constraint.")
                    opening_tone, opening_bg, opening_title, opening_copy = decision_message(
                        proposal_df,
                        covered_must < len(st.session_state.must_rides),
                    )
                    st.markdown(
                        f'<div class="opening-status" style="--tone:{opening_tone};--decision-bg:{opening_bg}"><b>{escape(opening_title)}</b><p>{escape(opening_copy)}</p></div>',
                        unsafe_allow_html=True,
                    )
                with st.container(key="preview_action"):
                    nav_space, nav_button = st.columns([1.65, 1.35])
                    with nav_button:
                        st.button(
                            "Review the proposed route  →",
                            width="stretch",
                            disabled=proposal is None,
                            type="primary",
                            on_click=prepare_route_review if proposal is not None else None,
                            args=(proposal,) if proposal is not None else (),
                        )

        elif current_step == 2:
            trip_start = pd.Timestamp(st.session_state.trip_start)
            trip_days = int(st.session_state.trip_days)
            planned_dates = [trip_start + pd.Timedelta(days=offset) for offset in range(trip_days)]
            considered = list(st.session_state.considered_parks)
            must_parks = {str(ride_lookup[item]["park_name"]) for item in st.session_state.must_rides}
            proposal = propose_route(reference, planned_dates, considered, must_parks, st.session_state.ticket)
            if proposal is None:
                st.session_state.flow_step = 1
                st.rerun()

            work_heading(
                "Review the system-designed route",
                "The proposal already covers the visitor's constraints. Editing the park assignment is optional.",
                "STEP 2 · DECISION REVIEW",
            )
            proposed_df = route_frame(reference, proposal)
            final_route = proposal
            if st.session_state.customise_route:
                final_route = [
                    (
                        day_number,
                        when,
                        st.session_state.get(f"route_park_{index}", default_park)
                        if st.session_state.get(f"route_park_{index}", default_park) in considered
                        else default_park,
                    )
                    for index, (day_number, when, default_park) in enumerate(proposal)
                ]
            final_df = route_frame(reference, final_route)
            final_must_coverage, must_coverage_label = must_do_coverage(
                final_df,
                list(st.session_state.must_rides),
                ride_lookup,
            )
            top1, top2, top3 = st.columns(3)
            top1.metric("Historical trip pressure", f"{final_df['index'].mean():.2f}×", border=True, help=TRIP_PRESSURE_HELP)
            top2.metric("Higher-pressure visits", f"{int((final_df['index'] >= HIGH_INDEX).sum())} of {len(final_df)}", border=True, help=HIGH_PRESSURE_HELP)
            top3.metric("Must-dos in scheduled parks", must_coverage_label, border=True, help=MUST_DO_HELP)
            if not st.session_state.must_rides:
                st.info("No must-do attractions selected. The route has no attraction-based park constraint.")
            st.caption(
                "Planning KPIs use the fixed 2015–2019 and 2022–2025 historical baseline. "
                "The live header is a separate current-status check: it is requested when the app reruns after "
                "an interaction or reload, and each response is cached for five minutes; the page does not refresh itself."
            )

            st.toggle("I want to adjust the proposed park assignment", key="customise_route")
            if st.session_state.customise_route:
                for row_start in range(0, len(proposal), 4):
                    row_routes = proposal[row_start:row_start + 4]
                    edit_cols = st.columns(min(4, len(row_routes)))
                    for column, (offset, (day_number, when, default_park)) in zip(edit_cols[:len(row_routes)], enumerate(row_routes), strict=True):
                        index = row_start + offset
                        key = f"route_park_{index}"
                        if key not in st.session_state or st.session_state[key] not in considered:
                            st.session_state[key] = default_park
                        with column:
                            st.selectbox(f"Day {day_number} · {when.strftime('%a %b %d')}", considered, key=key, format_func=lambda park: f"{PARK_ICONS[park]}  {park}")
            duplicate_hopper = has_duplicate_hopper_parks(final_route)
            if duplicate_hopper:
                st.error("A Park Hopper day needs two different parks.")

            missing_must_dos = final_must_coverage < len(st.session_state.must_rides)
            average_change = final_df["index"].mean() / proposed_df["index"].mean() - 1
            tone, bg, title, copy = decision_message(
                final_df,
                missing_must_dos,
                average_change,
                bool(st.session_state.customise_route),
            )
            st.markdown(f'<div class="decision-bar"><div class="decision-main" style="--tone:{tone};--decision-bg:{bg}"><b>{escape(title)}</b><p>{escape(copy)}</p></div><div class="decision-score"><div><strong>{final_df["index"].mean():.2f}×</strong><span>selected route</span></div><div><strong>{average_change:+.1%}</strong><span>vs system draft</span></div></div></div>', unsafe_allow_html=True)

            chart_col, reason_col = st.columns([1.05, .95], gap="medium")
            with chart_col:
                fig, axis = plt.subplots(figsize=(7.2, 2.45), facecolor="#FFFEFC")
                axis.set_facecolor("#FFFEFC")
                values = final_df["index"].to_numpy()
                colors = [PARK_COLORS[park] for park in final_df["park"]]
                labels = [f"Day {row.day} · {PARK_SHORT[row.park]}\n{pd.Timestamp(row.date).strftime('%b %d')}" for row in final_df.itertuples()]
                bars = axis.bar(np.arange(len(values)), values, color=colors, width=.58)
                axis.axhline(1.0, color=INK, linewidth=1.1, linestyle=(0, (4, 4)))
                axis.axhline(HIGH_INDEX, color=CORAL, linewidth=1.1, linestyle=(0, (2, 3)))
                axis.bar_label(bars, labels=[f"{value:.2f}×" for value in values], padding=3, fontsize=9, color=INK)
                axis.set_xticks(np.arange(len(values)), labels)
                axis.set_ylabel("Historical pressure index", fontsize=10.5, color=INK, fontweight="bold")
                axis.set_ylim(0, max(1.38, float(values.max()) * 1.18))
                axis.spines[["top", "right", "left"]].set_visible(False)
                axis.spines["bottom"].set_color("#D7D2C8")
                axis.tick_params(colors=INK, labelsize=9.5)
                axis.grid(axis="y", color="#D8D4CA", alpha=.55, linewidth=.7)
                axis.set_axisbelow(True)
                fig.tight_layout(pad=.8)
                st.pyplot(fig)
                plt.close(fig)
                st.caption(
                    "MK = Magic Kingdom · EP = Epcot · HS = Hollywood Studios · AK = Animal Kingdom. "
                    "Each index is relative to that park's own corresponding-year mean (1.00×). Indices do not "
                    "compare actual wait minutes across parks; a route-index decrease is not the same percentage "
                    "of queue-time savings. The 1.10× line is a manager review rule, not a validated prediction limit."
                )
            with reason_col:
                rationale_rows = []
                for route_index, row in enumerate(final_df.itertuples()):
                    must_here = sum(1 for item in st.session_state.must_rides if ride_lookup[item]["park_name"] == row.park)
                    alternative_indexes = [float(estimate(reference, pd.Timestamp(row.date), park)["index"]) for park in considered]
                    lowest_allowed = min(alternative_indexes)
                    if must_here:
                        rationale = f"protects {must_here} must-do(s)"
                    elif st.session_state.customise_route and row.park != proposal[route_index][2]:
                        rationale = "manager manual selection"
                    elif row.index <= lowest_allowed + .02:
                        rationale = "lowest comparable pressure among allowed parks"
                    else:
                        rationale = "balances park variety within constraints"
                    rationale_rows.append(f'<div class="swap"><b>DAY {row.day}</b><span>{escape(row.park)} · {rationale}</span><em>{row.index:.2f}×</em></div>')
                flagged_count = int((final_df["index"] >= HIGH_INDEX).sum())
                coverage_note = ""
                if st.session_state.customise_route and final_df["park"].nunique() != proposed_df["park"].nunique():
                    coverage_note = f' The custom route covers {final_df["park"].nunique()} park(s), versus {proposed_df["park"].nunique()} in the system draft.'
                manager_action = (
                    f"<b>Manager action:</b> Review the {flagged_count} flagged visit(s), retain must-do coverage, and document any manual change before releasing the visitor brief.{coverage_note}"
                    if flagged_count
                    else f"<b>Manager action:</b> No threshold exception is present. Confirm current hours and closures before releasing the visitor brief.{coverage_note}"
                )
                st.markdown(
                    f'''<section class="route-rationale-panel">
                    <div class="swap-list">{"".join(rationale_rows)}</div>
                    <div class="manager-action">{manager_action}</div>
                    </section>''',
                    unsafe_allow_html=True,
                )

            back_col, spacer, next_col = st.columns([.8, 1.4, 1])
            with back_col:
                st.button("← Back to trip brief", width="stretch", on_click=navigate, args=(1,))
            with next_col:
                st.button(
                    "Create visitor travel plan  →",
                    width="stretch",
                    disabled=duplicate_hopper or missing_must_dos,
                    type="primary",
                    on_click=accept_route,
                    args=(final_route,),
                )

        elif current_step == 3:
            route = st.session_state.get("accepted_route") or st.session_state.get("proposed_route")
            if not route:
                st.session_state.flow_step = 1
                st.rerun()
            final_df = route_frame(reference, route)
            trip_start = pd.Timestamp(st.session_state.trip_start)
            trip_end = trip_start + pd.Timedelta(days=int(st.session_state.trip_days) - 1)
            st.markdown(f'<section class="final-banner"><div><h2>Your Orlando park plan is ready</h2><p>{trip_start.strftime("%b %d")} – {trip_end.strftime("%b %d, %Y")} · {st.session_state.trip_days} Disney day(s) · {escape(st.session_state.ticket)} · {escape(st.session_state.pace)} rhythm</p></div><span class="final-badge">VISITOR TRAVEL BRIEF · {escape(TEAM_NAME.upper())}</span></section>', unsafe_allow_html=True)
            summary_cols = st.columns(3)
            summary_cols[0].metric("Historical trip pressure", f"{final_df['index'].mean():.2f}×", border=True, help=TRIP_PRESSURE_HELP)
            summary_cols[1].metric("Higher-pressure visits", f"{int((final_df['index'] >= HIGH_INDEX).sum())} of {len(final_df)}", border=True, help=HIGH_PRESSURE_HELP)
            accepted_parks = set(final_df["park"])
            protected_must_dos = sum(
                1 for item in st.session_state.must_rides
                if ride_lookup[item]["park_name"] in accepted_parks
            )
            protected_label = f"{protected_must_dos} / {len(st.session_state.must_rides)}" if st.session_state.must_rides else "None selected"
            summary_cols[2].metric("Must-dos in scheduled parks", protected_label, border=True, help=MUST_DO_HELP)
            if not st.session_state.must_rides:
                st.info("No must-do attractions were selected. Extra recommendations follow the chosen trip rhythm.")

            day_groups = list(final_df.groupby("day", sort=True))
            listed_attractions: set[str] = set()
            parks_with_must_dos_listed: set[str] = set()
            for row_start in range(0, len(day_groups), 4):
                cols = st.columns(min(4, len(day_groups) - row_start))
                for column, (day_number, day_rows) in zip(cols, day_groups[row_start:row_start + 4], strict=True):
                    with column:
                        parks_for_day = day_rows["park"].tolist()
                        date_for_day = pd.Timestamp(day_rows.iloc[0]["date"])
                        park_title = " + ".join(f"{PARK_ICONS[park]} {park}" for park in parks_for_day)
                        color = PARK_COLORS[parks_for_day[0]]
                        attraction_lines: list[str] = []
                        for park in parks_for_day:
                            priorities, backup = attraction_priorities(
                                rides,
                                park,
                                list(st.session_state.must_rides),
                                st.session_state.pace,
                                excluded_names=listed_attractions,
                                include_must=park not in parks_with_must_dos_listed,
                            )
                            parks_with_must_dos_listed.add(park)
                            for priority in priorities:
                                marker = "Must-do" if priority["is_must"] else "Prepare"
                                pass_label = {"single_pass": "Single Pass", "multi_pass": "Multi Pass", "none": "No pass label"}.get(str(priority.get("ll_class")), "Verify access")
                                attraction_lines.append(f"<p><b>{marker}:</b> {escape(str(priority['ride_name']))} · source avg {float(priority['minutes']):.0f} min · {pass_label}</p>")
                                listed_attractions.add(str(priority["ride_name"]))
                            if backup:
                                attraction_lines.append(f"<p><b>Flexible backup:</b> {escape(str(backup['ride_name']))} · source avg {float(backup['minutes']):.0f} min</p>")
                                listed_attractions.add(str(backup["ride_name"]))
                        st.markdown(f'<article class="final-day" style="--park:{color}"><small>DAY {day_number} · {date_for_day.strftime("%A, %B %d")}</small><h3>{escape(park_title)}</h3>{"".join(attraction_lines)}</article>', unsafe_allow_html=True)

            stay_guidance = {
                "Disney Resort hotel": "Confirm current resort transportation and any early-entry benefit attached to the booking; a midday hotel break may be operationally realistic.",
                "Other Orlando hotel": "Protect an arrival and return-transfer buffer; do not assume resort transportation or guest-entry benefits.",
                "Not decided": "Choose the hotel before locking arrival times because transport and eligibility can change the practical route.",
            }[st.session_state.hotel]
            access_guidance = {
                "Yes": "Early entry is noted; verify the eligible park and current operating terms.",
                "No": "No early-entry advantage is assumed.",
                "Unsure": "Early entry is not assumed until eligibility is confirmed.",
            }[st.session_state.early_entry]
            st.markdown(
                f'''<section class="trip-checks">
                <div class="trip-check"><b>Stay &amp; entry</b><p><strong>Hotel:</strong> {escape(st.session_state.hotel)} · <strong>Early entry:</strong> {escape(st.session_state.early_entry)}. {escape(stay_guidance)} {escape(access_guidance)}</p></div>
                <div class="trip-check"><b>Before each park day</b><p>Recheck official hours, closures, and ticket rules before acting.</p></div>
                </section>''',
                unsafe_allow_html=True,
            )
            back_col, save_col = st.columns([1, 1])
            with back_col:
                st.button("← Refine the route", width="stretch", on_click=navigate, args=(2,))
            with save_col:
                st.button("Save this itinerary  →", width="stretch", type="primary", on_click=save_itinerary)

        else:
            route = st.session_state.get("accepted_route") or st.session_state.get("proposed_route")
            if not route:
                st.session_state.flow_step = 1
                st.rerun()
            intro_items = [
                (3, -12, .00, 2.15, 44, 34, "#FF6B8E", "-7deg"),
                (9, -24, .12, 2.50, -36, 46, "#FFD05A", "5deg"),
                (15, -16, .28, 2.25, 32, 38, "#51C7B7", "-4deg"),
                (21, -28, .05, 2.75, -46, 42, "#7A65E8", "8deg"),
                (28, -10, .35, 2.35, 38, 50, "#FF8A5B", "-6deg"),
                (35, -22, .18, 2.65, -28, 36, "#55A9F6", "4deg"),
                (42, -30, .42, 2.45, 48, 44, "#E875D4", "-8deg"),
                (49, -14, .08, 2.20, -40, 40, "#FF6B8E", "6deg"),
                (56, -26, .24, 2.70, 34, 48, "#FFD05A", "-5deg"),
                (63, -18, .46, 2.30, -44, 35, "#51C7B7", "7deg"),
                (70, -32, .14, 2.55, 30, 43, "#7A65E8", "-6deg"),
                (77, -12, .32, 2.80, -38, 51, "#FF8A5B", "5deg"),
                (84, -25, .03, 2.40, 42, 37, "#55A9F6", "-7deg"),
                (91, -17, .38, 2.60, -32, 45, "#E875D4", "6deg"),
                (97, -29, .20, 2.18, 28, 39, "#FF6B8E", "-4deg"),
            ]
            ambient_items = [
                ("✨", 4, -8, 14, -18), ("🎡", 10, -3, 17, 26), ("⭐", 18, -12, 16, -24),
                ("🎆", 27, -6, 19, 32), ("🎠", 36, -14, 18, -28), ("✨", 45, -4, 15, 24),
                ("🎢", 54, -10, 18, -30), ("⭐", 63, -2, 16, 28), ("🎆", 72, -13, 19, -34),
                ("☀️", 81, -5, 17, 24), ("✨", 90, -11, 15, -22), ("⭐", 97, -7, 18, -18),
            ]
            intro_celebration_html = "".join(
                f'<span class="color-balloon" style="--x:{x}%;--start:{start}vh;--delay:{delay}s;--duration:{duration}s;--drift:{drift}px;--size:{size}px;--color:{color};--string-tilt:{tilt}"></span>'
                for x, start, delay, duration, drift, size, color, tilt in intro_items
            )
            ambient_celebration_html = "".join(
                f'<span style="--x:{x}%;--delay:{delay}s;--duration:{duration}s;--drift:{drift}px">{symbol}</span>'
                for symbol, x, delay, duration, drift in ambient_items
            )
            trip_start = pd.Timestamp(st.session_state.trip_start)
            trip_end = trip_start + pd.Timedelta(days=int(st.session_state.trip_days) - 1)
            parks_saved = []
            for _, _, park in route:
                if park not in parks_saved:
                    parks_saved.append(park)
            park_chips = "".join(f"<span>{PARK_ICONS[park]} {escape(park)}</span>" for park in parks_saved)
            st.markdown(
                f'''<section class="success-shell"><div class="success-card">
                <div class="success-icon">✓</div>
                <h2>Itinerary saved for this session</h2>
                <div class="celebrate">🎉 Your Orlando adventure is ready — have a wonderful trip! 🎠</div>
                <p>Your QueueSense itinerary is available only in the current browser session; it has not been saved to an account or permanent database. You can review the finished plan or return to the beginning and adjust any preference.</p>
                <div class="success-chips"><span>📅 {trip_start.strftime("%b %d")} – {trip_end.strftime("%b %d, %Y")}</span><span>🧭 {st.session_state.trip_days} park day(s)</span>{park_chips}</div>
                </div></section>''',
                unsafe_allow_html=True,
            )
            with st.container(key="success_actions"):
                edit_col, view_col = st.columns(2, gap="medium", vertical_alignment="bottom")
                with edit_col:
                    st.button("← Return to page 1 and edit", width="stretch", on_click=navigate, args=(1,))
                with view_col:
                    st.button("View the saved travel plan", width="stretch", type="primary", on_click=navigate, args=(3,))

    if intro_celebration_html:
        st.markdown(f'<div class="full-screen-celebration balloon-intro" aria-hidden="true">{intro_celebration_html}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="full-screen-celebration ambient-celebration" aria-hidden="true">{ambient_celebration_html}</div>', unsafe_allow_html=True)

    theme = STEP_THEMES.get(current_step, STEP_THEMES[1])
    st.markdown(f'<div class="source-foot"><a href="https://queue-times.com/en-US" target="_blank"><b>Powered by Queue-Times.com</b></a> · Photo: <a href="{theme["page"]}" target="_blank">{escape(theme["credit"])}</a> · Wikimedia Commons</div>', unsafe_allow_html=True)
    scroll_to_top_if_needed()
