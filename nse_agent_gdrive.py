#!/usr/bin/env python3
"""
NSE Smart Money Agent - Google Drive Version

Workflow:
1. You download Bulk + Block CSVs from NSE website (2 min, once a week)
2. Upload both files to a Google Drive folder
3. Run this agent - it reads from Drive, builds heatmap, emails you

Setup:
  pip3 install requests pandas numpy google-auth google-auth-oauthlib google-api-python-client

Run:
  cd ~/nse-smart-money
  NSE_EMAIL_FROM=... NSE_EMAIL_TO=... NSE_EMAIL_PASSWORD=... \
  GDRIVE_BULK_ID=<file_id> GDRIVE_BLOCK_ID=<file_id> \
  python3 nse_agent_gdrive.py
"""

import os, sys, io, time, json, smtplib, warnings
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

warnings.filterwarnings("ignore")

# ── Config ────────────────────────────────────────────────────────────────────
EMAIL_FROM     = os.environ.get("NSE_EMAIL_FROM", "")
EMAIL_TO       = os.environ.get("NSE_EMAIL_TO", "")
EMAIL_PASSWORD = os.environ.get("NSE_EMAIL_PASSWORD", "")
GDRIVE_BULK_ID  = os.environ.get("GDRIVE_BULK_ID", "")   # Google Drive file ID for bulk CSV
GDRIVE_BLOCK_ID = os.environ.get("GDRIVE_BLOCK_ID", "")  # Google Drive file ID for block CSV
TOP_N           = 50
SCRIPT_DIR      = Path(__file__).parent

KNOWN_MCAP = {
    'BHARTIARTL':1050000,'INDIGO':130000,'ITC':540000,'KOTAKBANK':380000,
    'BAJAJFINSV':280000,'HINDZINC':190000,'HEROMOTOCO':80000,'ETERNAL':240000,
    'POLYCAB':75000,'SONACOMS':22000,'ORKLAINDIA':18000,'TATAELXSI':38000,
    'INDUSINDBK':55000,'BHARATFORG':60000,'CONCOR':45000,'TIINDIA':28000,
    'IRCTC':68000,'INNOVISION':1800,'ASTRAL':35000,'ACC':38000,
    'PAYTM':55000,'SAGILITY':25000,'ABCAPITAL':35000,'BAJAJHFL':90000,
    'ADANIGREEN':195000,'SWIGGY':65000,'PNBHOUSING':25000,'360ONE':45000,
    'APOLLOHOSP':88000,'FORTIS':62000,'LODHA':48000,'ZEEL':8000,
    'HEG':12000,'SUDARSCHEM':8500,'INDSWFTLAB':1200,'BLACKBUCK':9000,
    'GALLANTT':4500,'DELHIVERY':18000,'EMBASSY':42000,'NEWGEN':14000,
    'APOLLOPIPE':3500,'RELIGARE':8000,'RELIANCE':1050000,'TCS':1350000,
    'HDFCBANK':1200000,'INFY':620000,'ICICIBANK':800000,'HINDUNILVR':560000,
    'SBIN':720000,'AXISBANK':360000,'WIPRO':250000,'HCLTECH':340000,
    'MARUTI':360000,'ULTRACEMCO':200000,'TITAN':320000,'BAJFINANCE':420000,
    'SUNPHARMA':340000,'ONGC':280000,'NTPC':320000,'POWERGRID':280000,
    'ADANIENT':240000,'ADANIPORTS':230000,'TATAMOTORS':280000,'TATASTEEL':180000,
    'JSWSTEEL':170000,'NESTLEIND':220000,'DIVISLAB':110000,'CIPLA':100000,
    'DRREDDY':110000,'TECHM':140000,'GRASIM':160000,'HINDALCO':150000,
    'COALINDIA':240000,'BPCL':130000,'EICHERMOT':115000,'BRITANNIA':115000,
    'TATACONSUM':75000,'PIDILITIND':115000,'SBILIFE':145000,'HDFCLIFE':135000,
    'ICICIPRULI':85000,'BAJAJ-AUTO':115000,'M&M':200000,'ASIANPAINT':175000,
    'LTIM':130000,'HAVELLS':70000,'SIEMENS':90000,'ABB':80000,
    'AMBUJACEM':90000,'DMART':260000,'NYKAA':40000,'LT':480000,
    'TATAPOWER':80000,'TORNTPHARM':95000,'MPHASIS':50000,'PERSISTENT':60000,
    'COFORGE':35000,'LTTS':40000,'ZOMATO':200000,'IRFC':70000,
    'RVNL':50000,'NMDC':50000,'SAIL':35000,'GAIL':95000,
    'PETRONET':50000,'HPCL':65000,'IOC':135000,'ICICIGI':90000,
    'HDFCAMC':80000,'CHOLAFIN':90000,'SHRIRAMFIN':95000,'MUTHOOTFIN':65000,
    'WABAG':8000,'SHAILY':3500,'ADFFOODS':2000,'SEITINVIT':5000,
    'ORIENTELEC':4000,'UGROCAP':3000,'AQYLON':1500,'ATULAUTO':2000,
    'ROLEXRINGS':4000,'ARE&M':12000,'MUFIN':2000,'IDEAFORGE':3500,
    'BHARATWIRE':2500,'LEMONTREE':12000,'APOLLO':8000,'CRAFTSMAN':8000,
    'EIEL':6000,'SCI':8000,'ONESOURCE':3000,'TRITURBINE':18000,
    'SWSOLAR':5000,'ANGELONE':12000,'GMDCLTD':8000,'FSL':8000,
}


# ── Google Drive download (public share link) ──────────────────────────────────
def download_from_gdrive(file_id, label):
    """
    Download a CSV from Google Drive using file ID.
    File must be shared as 'Anyone with the link can view'.
    """
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    print(f"  Downloading {label} from Google Drive...")
    try:
        session = requests.Session()
        r = session.get(url, timeout=60)

        # Handle Google's virus scan warning for large files
        if "virus scan warning" in r.text.lower() or "download_warning" in r.url:
            # Get confirmation token
            for key, value in r.cookies.items():
                if key.startswith("download_warning"):
                    url = f"https://drive.google.com/uc?export=download&confirm={value}&id={file_id}"
                    r = session.get(url, timeout=60)
                    break

        if r.status_code == 200 and len(r.content) > 500:
            content = r.text
            df = pd.read_csv(io.StringIO(content))
            print(f"  {label}: {len(df)} rows downloaded")
            return df
        else:
            print(f"  {label}: failed (status={r.status_code}, size={len(r.content)})")
            return pd.DataFrame()
    except Exception as e:
        print(f"  {label} download error: {e}")
        return pd.DataFrame()


# ── Parse CSV ─────────────────────────────────────────────────────────────────
def clean_num(x):
    try: return float(str(x).replace(',', '').strip())
    except: return 0.0


def parse_nse_df(df, source):
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ","_").replace("/","_").replace(".","").replace("(","").replace(")","") for c in df.columns]

    col_map = {
        "symbol":"symbol", "scrip_code":"symbol",
        "security_name":"security", "scrip_name":"security",
        "client_name":"client", "name_of_acquirer_seller":"client",
        "buy___sell":"side", "buy_sell":"side", "transaction_type":"side",
        "quantity_traded":"qty", "quantity":"qty", "no_of_shares":"qty",
        "trade_price___wght_avg_price":"price", "price":"price",
        "weighted_average_price":"price",
        "date":"date", "trade_date":"date",
    }
    df = df.rename(columns={c: col_map[c] for c in df.columns if c in col_map})
    for c in ["symbol","qty","price","side","client","date","security"]:
        if c not in df.columns:
            df[c] = ""

    records = []
    cutoff = datetime.today().date() - timedelta(days=400)
    for _, row in df.iterrows():
        try:
            sym   = str(row["symbol"]).strip().upper()
            side  = str(row["side"]).strip().upper()
            qty   = clean_num(row["qty"])
            price = clean_num(row["price"])
            cli   = str(row["client"]).strip()
            sec   = str(row.get("security","")).strip()
            if not sym or sym in ("","NAN","SYMBOL") or price == 0:
                continue
            dt = pd.to_datetime(str(row["date"]).strip(), dayfirst=True, errors="coerce")
            if pd.isna(dt) or dt.date() < cutoff:
                continue
            val_cr = qty * price / 1e7
            is_buy = side.startswith("B")
            records.append({
                "source": source, "symbol": sym, "security": sec,
                "client": cli, "side": "BUY" if is_buy else "SELL",
                "qty": qty, "price": price, "val_cr": val_cr,
                "signed": val_cr if is_buy else -val_cr,
                "date": dt, "month": dt.to_period("M"),
            })
        except Exception:
            continue

    print(f"  {source} parsed: {len(records)} valid rows")
    return pd.DataFrame(records) if records else pd.DataFrame()


# ── Analytics ─────────────────────────────────────────────────────────────────
def wavg(grp):
    tq = grp["qty"].sum()
    return round(float((grp["price"] * grp["qty"]).sum() / tq), 2) if tq > 0 else 0.0


def summarise(sub):
    rows = []
    for sym, grp in sub.groupby("symbol"):
        sec = grp["security"].iloc[0] if "security" in grp.columns else ""
        net = round(float(grp["signed"].sum()), 2)
        buy_g  = grp[grp["side"] == "BUY"]
        sell_g = grp[grp["side"] == "SELL"]
        buy_avg  = wavg(buy_g)  if not buy_g.empty else 0.0
        sell_avg = wavg(sell_g) if not sell_g.empty else 0.0
        tb = buy_g.groupby("client")["val_cr"].sum().idxmax() if not buy_g.empty else "\u2014"
        ts = sell_g.groupby("client")["val_cr"].sum().idxmax() if not sell_g.empty else "\u2014"
        rows.append({"s": sym, "n": sec, "net": net,
                     "buy_avg": buy_avg, "sell_avg": sell_avg,
                     "tb": tb, "ts": ts})
    rows.sort(key=lambda x: x["net"], reverse=True)
    return rows


def build_monthly(df, syms):
    months  = sorted(df["month"].unique())
    sec_map = df.drop_duplicates("symbol").set_index("symbol")["security"].to_dict()
    result  = {}
    for sym in syms:
        grp = df[df["symbol"] == sym]
        mdata = {}
        for m in months:
            pg = grp[grp["month"] == m]
            net_v  = round(float(pg["signed"].sum()), 2)
            buy_pg = pg[pg["side"] == "BUY"]
            sel_pg = pg[pg["side"] == "SELL"]
            ba = wavg(buy_pg) if not buy_pg.empty else 0.0
            sa = wavg(sel_pg) if not sel_pg.empty else 0.0
            mdata[str(m)] = {"net": net_v, "buy_avg": ba, "sell_avg": sa,
                             "price": ba if net_v >= 0 else sa}
        result[sym] = {"sec": sec_map.get(sym, sym), "months": mdata}
    return result, [str(m) for m in months]


def build_daily(df, syms, trading_days):
    df_7d   = df[df["date"].isin(trading_days)]
    sec_map = df.drop_duplicates("symbol").set_index("symbol")["security"].to_dict()
    result  = {}
    for sym in syms:
        grp = df_7d[df_7d["symbol"] == sym]
        ddata = {}
        for d in trading_days:
            pg = grp[grp["date"] == d]
            net_v  = round(float(pg["signed"].sum()), 2)
            buy_pg = pg[pg["side"] == "BUY"]
            sel_pg = pg[pg["side"] == "SELL"]
            ba = wavg(buy_pg) if not buy_pg.empty else 0.0
            sa = wavg(sel_pg) if not sel_pg.empty else 0.0
            key = str(d.date()) if hasattr(d, 'date') else str(d)
            ddata[key] = {"net": net_v, "buy_avg": ba, "sell_avg": sa,
                          "price": ba if net_v >= 0 else sa}
        result[sym] = {"sec": sec_map.get(sym, sym), "days": ddata}
    return result, [str(d.date()) if hasattr(d,'date') else str(d) for d in trading_days]


def fetch_live_mcaps(syms, known):
    mcap    = dict(known)
    missing = [s for s in syms if not mcap.get(s)]
    if not missing:
        return mcap
    print(f"  Fetching {len(missing)} market caps from Yahoo...")
    for sym in missing:
        try:
            r = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}.NS?range=1d&interval=1d",
                timeout=6
            )
            mc = r.json()["chart"]["result"][0]["meta"].get("marketCap", 0)
            if mc: mcap[sym] = round(mc / 1e7)
        except: pass
        time.sleep(0.15)
    loaded = sum(1 for v in mcap.values() if v > 0)
    print(f"  Market caps: {loaded}/{len(syms)}")
    return mcap


# ── HTML Builder ───────────────────────────────────────────────────────────────
def build_html(data, mcap, run_date):
    js_data = json.dumps(data, separators=(',',':'))
    js_mcap = json.dumps({k:v for k,v in mcap.items() if v>0}, separators=(',',':'))

    css = """*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0d1117;color:#e2e8f0;font-size:13px}.wrap{padding:16px 20px}.hdr{background:linear-gradient(135deg,#0f1923,#1a2f4a);border-radius:10px;padding:16px 22px;margin-bottom:14px;border:1px solid #1e3a5f;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px}.hdr h1{font-size:17px;font-weight:600;color:#60a5fa}.hdr p{font-size:11px;color:#475569;margin-top:3px}.mcap-pill{font-size:11px;padding:4px 12px;border-radius:5px;background:#0f1923;border:1px solid #1e3a5f;color:#64748b}.mcap-pill.done{color:#4ade80;border-color:#166534}.tabs{display:flex;border-bottom:1px solid #1e293b;margin-bottom:14px}.tab{padding:9px 18px;font-size:13px;cursor:pointer;color:#64748b;border-bottom:2px solid transparent;background:none;border-top:none;border-left:none;border-right:none;font-family:inherit}.tab.on{color:#e2e8f0;border-bottom-color:#3b82f6;font-weight:500}.controls{display:flex;gap:8px;margin-bottom:12px;align-items:center;flex-wrap:wrap}.tgl{padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:500;border:1px solid #1e3a5f;background:transparent;color:#64748b;font-family:inherit}.tgl.on-buy{background:#052e16;color:#4ade80;border-color:#166534}.tgl.on-sell{background:#2d0707;color:#f87171;border-color:#7f1d1d}.info{font-size:11px;color:#334155;padding:4px 8px;background:#090d14;border-radius:4px;border:1px solid #1e293b}.hm-outer{overflow:auto;border:1px solid #1e293b;border-radius:8px;max-height:calc(100vh - 210px)}table.hm{border-collapse:collapse;white-space:nowrap}table.hm th{padding:8px 10px;text-align:center;font-size:10px;font-weight:500;color:#64748b;background:#090d14;border-right:1px solid #1e293b;border-bottom:2px solid #1e3a5f;position:sticky;top:0;z-index:3;min-width:115px}table.hm th.th-sym{text-align:left;position:sticky;left:0;z-index:4;min-width:165px}table.hm th.th-tot{position:sticky;right:0;z-index:4;border-left:2px solid #1e3a5f;min-width:140px}table.hm td.td-sym{padding:8px 10px;position:sticky;left:0;z-index:2;background:#0d1117;border-right:2px solid #1e293b;border-bottom:1px solid #111827;vertical-align:top;min-width:165px}.sn{font-weight:600;color:#e2e8f0;font-size:12px}.ss{font-size:10px;color:#475569;margin-top:1px}.sm{font-size:10px;color:#3b82f6;margin-top:2px;min-height:14px}.se{font-size:10px;color:#475569;margin-top:2px;max-width:155px;overflow:hidden;text-overflow:ellipsis}table.hm td.td-data{padding:0;border-right:1px solid #111827;border-bottom:1px solid #111827;vertical-align:top;min-width:115px}.ci{padding:6px 8px;min-height:52px;display:flex;flex-direction:column;justify-content:center;align-items:flex-end}.cn{font-family:'SF Mono',Menlo,Consolas,monospace;font-size:11px;font-weight:600;line-height:1.4}.cp{font-family:'SF Mono',Menlo,Consolas,monospace;font-size:10px;margin-top:2px;line-height:1.4}.ck{font-family:'SF Mono',Menlo,Consolas,monospace;font-size:10px;margin-top:1px;line-height:1.4;min-height:14px}table.hm td.td-tot{padding:8px 10px;position:sticky;right:0;z-index:2;background:#0d1117;border-left:2px solid #1e3a5f;border-bottom:1px solid #111827;vertical-align:top;min-width:140px}.tn{font-family:'SF Mono',Menlo,Consolas,monospace;font-size:12px;font-weight:600}.tp{font-family:'SF Mono',Menlo,Consolas,monospace;font-size:10px;margin-top:3px;color:#64748b}.tk{font-family:'SF Mono',Menlo,Consolas,monospace;font-size:10px;margin-top:2px;min-height:14px}"""

    js = f"""
const D={js_data};const MCAP={js_mcap};
const MONTHS=D.months;const MLBL=MONTHS.map(m=>{{const[y,mo]=m.split('-');return ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+mo-1]+"'"+y.slice(2)}});
const DAYS=D.days;const DLBL=DAYS.map(d=>{{const dt=new Date(d+'T00:00:00');return ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][dt.getDay()]+' '+dt.getDate()+' '+['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][dt.getMonth()]}});
let vs={{monthly:'buy',daily:'buy'}};const R=String.fromCharCode(8377);
function fCr(v){{v=+v;const s=v>0?'+':'';if(Math.abs(v)>=1000)return s+(v/1000).toFixed(1)+'K Cr';return s+v.toFixed(1)+' Cr';}}
function fP(v){{if(!v||v<1)return '';return R+Number(v).toLocaleString('en-IN',{{maximumFractionDigits:0}});}}
function fPct(net,sym){{const mc=MCAP[sym];if(!mc||mc<1)return '';const p=Math.abs(net)/mc*100;if(p<0.001)return '';return (net>=0?'+':'-')+p.toFixed(p>=1?1:2)+'% mcap';}}
function fMcap(sym){{const mc=MCAP[sym];if(!mc||mc<1)return '';if(mc>=100000)return R+(mc/100000).toFixed(1)+'L Cr';if(mc>=1000)return R+(mc/1000).toFixed(0)+'K Cr';return R+mc+' Cr';}}
function cs(v,mx){{if(Math.abs(v)<0.01)return{{bg:'#090d14',tc:'#334155',t2:'#334155'}};const a=Math.min(0.9,Math.abs(v)/mx*0.82+0.1).toFixed(2);const bg=v>0?'rgba(22,101,52,'+a+')':'rgba(127,29,29,'+a+')';const bright=Math.abs(v)/mx>0.18;const tc=bright?'#fff':(v>0?'#86efac':'#fca5a5');const t2=bright?'rgba(255,255,255,0.65)':(v>0?'rgba(134,239,172,0.6)':'rgba(252,165,165,0.6)');return{{bg,tc,t2}};}}
function render(type,view){{const isMon=type==='monthly';const periods=isMon?MONTHS:DAYS;const labels=isMon?MLBL:DLBL;const dmap=isMon?D.monthly:D.daily;const smap=isMon?D.monthly_summary:D.daily_summary;const syms=view==='buy'?(isMon?D.buy_syms:D.buy_syms_7d):(isMon?D.sell_syms:D.sell_syms_7d);let mx=0;syms.forEach(s=>{{const d=dmap[s];if(!d)return;const pd=isMon?d.months:d.days;periods.forEach(p=>{{const v=(pd[p]||{{}}).net||0;if(Math.abs(v)>mx)mx=Math.abs(v);}});}});if(mx===0)mx=1;let h='<table class="hm"><thead><tr><th class="th-sym">Symbol</th>';labels.forEach(l=>h+='<th>'+l+'</th>');h+='<th class="th-tot">1Y Total</th></tr></thead><tbody>';syms.forEach(sym=>{{const d=dmap[sym];if(!d)return;const pd=isMon?d.months:d.days;const s=smap[sym]||{{}};const ent=view==='buy'?(s.tb||''):(s.ts||'');const tn=s.net||0;const tp=tn>=0?(s.buy_avg||0):(s.sell_avg||0);const tpct=fPct(tn,sym);const tc=tn>=0?'#4ade80':'#f87171';const tpc=tn>=0?'#86efac':'#fca5a5';h+='<tr><td class="td-sym"><div class="sn">'+sym+'</div><div class="ss">'+d.sec.slice(0,22)+'</div><div class="sm" id="mc-'+sym+'">'+fMcap(sym)+'</div>'+(ent?'<div class="se">'+(view==='buy'?'&#8679; ':'&#8681; ')+ent.slice(0,22)+'</div>':'')+'</td>';periods.forEach(p=>{{const cell=pd[p]||{{net:0,buy_avg:0,sell_avg:0}};const v=cell.net;const pr=v>=0?(cell.buy_avg||0):(cell.sell_avg||0);if(Math.abs(v)<0.01){{h+='<td class="td-data"><div class="ci" style="background:#090d14"></div></td>';return;}}const c=cs(v,mx);const pct=fPct(v,sym);h+='<td class="td-data"><div class="ci" style="background:'+c.bg+'"><div class="cn" style="color:'+c.tc+'">'+fCr(v)+'</div>'+(pr?'<div class="cp" style="color:'+c.t2+'">'+fP(pr)+'</div>':'')+(pct?'<div class="ck" style="color:'+c.t2+'">'+pct+'</div>':'<div class="ck"></div>')+'</div></td>';}});h+='<td class="td-tot"><div class="tn" style="color:'+tc+'">'+fCr(tn)+'</div>'+(tp?'<div class="tp">'+fP(tp)+' '+(tn>=0?'buy':'sell')+' avg</div>':'')+(tpct?'<div class="tk" style="color:'+tpc+'">'+tpct+'</div>':'')+'</td></tr>';}});h+='</tbody></table>';document.getElementById(type+'-wrap').innerHTML=h;}}
function sw(name,el){{document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));el.classList.add('on');document.getElementById('tab-monthly').style.display=name==='monthly'?'block':'none';document.getElementById('tab-daily').style.display=name==='daily'?'block':'none';}}
function setView(t,v){{vs[t]=v;const px=t==='monthly'?'tm':'td';document.getElementById(px+'-buy').className='tgl'+(v==='buy'?' on-buy':'');document.getElementById(px+'-sell').className='tgl'+(v==='sell'?' on-sell':'');render(t,v);}}
async function fetchMissingMcaps(){{const pill=document.getElementById('mcap-pill');const allSyms=[...new Set([...D.buy_syms,...D.sell_syms,...D.buy_syms_7d,...D.sell_syms_7d])];const missing=allSyms.filter(s=>!MCAP[s]||MCAP[s]===0);let loaded=Object.values(MCAP).filter(v=>v>0).length;const total=allSyms.length;if(missing.length===0){{pill.className='mcap-pill done';pill.textContent='\u2713 Market caps: '+loaded+'/'+total;return;}}for(let i=0;i<missing.length;i+=5){{const batch=missing.slice(i,i+5);await Promise.all(batch.map(async sym=>{{try{{const r=await fetch('https://query1.finance.yahoo.com/v8/finance/chart/'+sym+'.NS?interval=1d&range=1d');const d=await r.json();const mc=(((d||{{}}).chart||{{}}).result||[{{}}])[0]?.meta?.marketCap||0;if(mc>0){{MCAP[sym]=Math.round(mc/1e7);loaded++;const el=document.getElementById('mc-'+sym);if(el)el.textContent=fMcap(sym);}}}}catch{{}}}})));pill.textContent='\u29d6 '+loaded+'/'+total+' caps';await new Promise(res=>setTimeout(res,300));}}pill.className='mcap-pill done';pill.textContent='\u2713 '+loaded+'/'+total+' caps';render('monthly',vs.monthly);render('daily',vs.daily);}}
render('monthly','buy');render('daily','buy');fetchMissingMcaps();"""

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NSE Smart Money &mdash; {run_date}</title><style>{css}</style></head><body><div class="wrap"><div class="hdr"><div><h1>&#9889; NSE Smart Money Flow</h1><p>Bulk + Block Deals &nbsp;&middot;&nbsp; {run_date} &nbsp;&middot;&nbsp; Top {TOP_N} per view</p></div><div id="mcap-pill" class="mcap-pill">&#8987; Loading&hellip;</div></div><div class="tabs"><button class="tab on" onclick="sw('monthly',this)">&#128197; Monthly heatmap (1Y)</button><button class="tab" onclick="sw('daily',this)">&#128198; 7-day heatmap</button></div><div id="tab-monthly"><div class="controls"><button class="tgl on-buy" id="tm-buy" onclick="setView('monthly','buy')">&#8679; Top {TOP_N} net buyers</button><button class="tgl" id="tm-sell" onclick="setView('monthly','sell')">&#8681; Top {TOP_N} net sellers</button><span class="info">Net (Cr) &middot; Weighted avg price &middot; % of market cap</span></div><div class="hm-outer" id="monthly-wrap"></div></div><div id="tab-daily" style="display:none"><div class="controls"><button class="tgl on-buy" id="td-buy" onclick="setView('daily','buy')">&#8679; Top {TOP_N} net buyers</button><button class="tgl" id="td-sell" onclick="setView('daily','sell')">&#8681; Top {TOP_N} net sellers</button><span class="info">Net (Cr) &middot; Weighted avg price &middot; % of market cap</span></div><div class="hm-outer" id="daily-wrap"></div></div></div><script>{js}</script></body></html>"""


def send_email(html_path, run_date):
    msg = MIMEMultipart("mixed")
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg["Subject"] = f"\u26a1 NSE Smart Money \u2014 {run_date}"
    msg.attach(MIMEText(
        f"NSE Smart Money Flow \u2014 {run_date}\n\nHeatmap attached. Open in Chrome.",
        "plain"
    ))
    filename = f"NSE_SmartMoney_{run_date.replace(' ','_')}.html"
    with open(html_path, "rb") as f:
        part = MIMEBase("text","html")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        part.add_header("Content-Type", f'text/html; name="{filename}"')
        msg.attach(part)
    with smtplib.SMTP("smtp.gmail.com", 587) as srv:
        srv.ehlo(); srv.starttls(); srv.ehlo()
        srv.login(EMAIL_FROM, EMAIL_PASSWORD)
        srv.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    print(f"  \u2705 Email sent ({Path(html_path).stat().st_size//1024}KB)")


def main():
    today    = datetime.today()
    run_date = today.strftime("%d %b %Y")
    ts       = today.strftime("%Y%m%d_%H%M")
    print(f"\n\u26a1 NSE Smart Money Agent (Google Drive) \u2014 {run_date}")
    print("=" * 55)

    # ── Load data ────────────────────────────────────────────────────────────
    print("\nLoading data...")

    # Option 1: From Google Drive (if file IDs provided)
    bulk_df = block_df = pd.DataFrame()
    if GDRIVE_BULK_ID:
        bulk_df  = download_from_gdrive(GDRIVE_BULK_ID,  "Bulk")
        block_df = download_from_gdrive(GDRIVE_BLOCK_ID, "Block") if GDRIVE_BLOCK_ID else pd.DataFrame()
    else:
        # Option 2: From local CSV files
        print("  No Google Drive IDs set — reading local CSVs...")
        for name, var_name in [("bulk_1y.csv","bulk_df"),("block_1y.csv","block_df")]:
            path = SCRIPT_DIR / name
            if path.exists():
                df_raw = pd.read_csv(path)
                print(f"  {name}: {len(df_raw)} rows")
                if var_name == "bulk_df":
                    bulk_df = df_raw
                else:
                    block_df = df_raw
            else:
                print(f"  \u26a0\ufe0f  {name} not found")

    # Parse
    bulk_parsed  = parse_nse_df(bulk_df,  "BULK")
    block_parsed = parse_nse_df(block_df, "BLOCK")
    df = pd.concat([bulk_parsed, block_parsed], ignore_index=True)

    if df.empty:
        print("\n\u274c No data! Set GDRIVE_BULK_ID/GDRIVE_BLOCK_ID or place CSVs in script folder.")
        sys.exit(1)

    df = df.drop_duplicates(subset=["symbol","date","client","side","qty"]).dropna(subset=["date"])
    cutoff = today.date() - timedelta(days=400)
    df = df[df["date"].dt.date >= cutoff]

    print(f"\n  Final: {len(df)} rows \u00b7 {df['symbol'].nunique()} symbols")
    print(f"  Date range: {df['date'].min().date()} \u2192 {df['date'].max().date()}")
    print(f"  Months: {df['month'].nunique()}")

    # ── Process ──────────────────────────────────────────────────────────────
    print("\nProcessing...")
    all_rows = summarise(df)
    buy_syms  = [r["s"] for r in all_rows if r["net"] > 0][:TOP_N]
    sell_syms = [r["s"] for r in all_rows if r["net"] < 0][-TOP_N:][::-1]

    trading_days = sorted(df["date"].unique())[-7:]
    rows_7d      = summarise(df[df["date"].isin(trading_days)])
    buy_syms_7d  = [r["s"] for r in rows_7d if r["net"] > 0][:TOP_N]
    sell_syms_7d = [r["s"] for r in rows_7d if r["net"] < 0][-TOP_N:][::-1]

    all_syms = list(dict.fromkeys(buy_syms+sell_syms+buy_syms_7d+sell_syms_7d))
    print(f"  1Y: {len(buy_syms)} buyers, {len(sell_syms)} sellers")
    print(f"  7D: {len(buy_syms_7d)} buyers, {len(sell_syms_7d)} sellers")

    monthly_data, month_strs = build_monthly(df, list(dict.fromkeys(buy_syms+sell_syms)))
    daily_data,   day_strs   = build_daily(df, list(dict.fromkeys(buy_syms_7d+sell_syms_7d)), trading_days)

    row_map_1y = {r["s"]: r for r in all_rows}
    row_map_7d = {r["s"]: r for r in rows_7d}
    monthly_summary = {s: row_map_1y[s] for s in list(dict.fromkeys(buy_syms+sell_syms)) if s in row_map_1y}
    daily_summary   = {s: row_map_7d[s] for s in list(dict.fromkeys(buy_syms_7d+sell_syms_7d)) if s in row_map_7d}

    print("\nFetching market caps...")
    mcap = fetch_live_mcaps(all_syms, KNOWN_MCAP)

    print("\nBuilding HTML...")
    payload = {
        "months": month_strs, "days": day_strs,
        "buy_syms": buy_syms, "sell_syms": sell_syms,
        "buy_syms_7d": buy_syms_7d, "sell_syms_7d": sell_syms_7d,
        "monthly": monthly_data, "daily": daily_data,
        "monthly_summary": monthly_summary, "daily_summary": daily_summary,
        "today": str(df["date"].max())
    }
    html = build_html(payload, mcap, run_date)
    out  = Path(f"/tmp/NSE_SmartMoney_{ts}.html")
    out.write_text(html, encoding="utf-8")
    print(f"  Saved: {out} ({len(html)//1024}KB)")

    if EMAIL_FROM and EMAIL_PASSWORD:
        print("\nSending email...")
        send_email(str(out), run_date)

    print(f"\n\u2705 Done \u2014 {run_date}")


if __name__ == "__main__":
    main()
