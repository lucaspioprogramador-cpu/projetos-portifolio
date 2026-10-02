"""
Signal Preview Panel — componente visual para o Trading Bot Dashboard.

Como usar no main_app.py:
    from signal_preview_panel import render_signal_panel
    
    # Após calcular os indicadores (gerar_features_melhorada):
    render_signal_panel(ultimo_indicador, posicao_aberta, preco_compra, config)

Dependências: streamlit
"""

import streamlit.components.v1 as components


def render_signal_panel(
    indicadores: dict,
    posicao_aberta: bool = False,
    preco_compra: float = None,
    config: dict = None,
    confianca: float = 0.0,
    sinal_atual: str = "hold",
    height: int = 560,
):
    """
    Renderiza o painel visual de condições de compra/venda.

    Parâmetros:
        indicadores    : dicionário com os valores do último candle (saída de gerar_features_melhorada)
        posicao_aberta : True se há posição aberta
        preco_compra   : preço de entrada na posição aberta (ou None)
        config         : dicionário com os parâmetros da estratégia melhorada
        confianca      : confiança do modelo (0.0 – 1.0)
        sinal_atual    : 'buy', 'sell' ou 'hold'
        height         : altura em px do componente HTML
    """

    if config is None:
        config = {
            "min_confidence_buy": 0.60,
            "max_rsi_buy": 75,
            "min_adx": 20,
            "min_volume_ratio": 1.0,
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.03,
            "max_rsi_sell": 80,
            "min_confidence_sell": 0.50,
        }

    # ── extrair valores dos indicadores ──────────────────────────────────────
    rsi            = float(indicadores.get("rsi", 50))
    adx            = float(indicadores.get("adx", 0))
    macd           = float(indicadores.get("macd", 0))
    macd_signal    = float(indicadores.get("macd_signal", 0))
    macd_hist      = float(indicadores.get("macd_hist", 0))
    volume_ratio   = float(indicadores.get("volume_ratio", 1.0))
    close          = float(indicadores.get("close", 0))
    ma_5           = float(indicadores.get("ma_5", close))
    ma_20          = float(indicadores.get("ma_20", close))
    bb_position    = float(indicadores.get("bb_position", 0.5))

    lucro_pct = 0.0
    if posicao_aberta and preco_compra:
        lucro_pct = (close - preco_compra) / preco_compra

    # ── avaliar condições de COMPRA ───────────────────────────────────────────
    buy_conditions = [
        {
            "label": f"Modelo prevê alta (confiança ≥ {config['min_confidence_buy']:.0%})",
            "ok": sinal_atual == "buy" or confianca >= config["min_confidence_buy"],
            "value": f"{confianca:.1%}",
        },
        {
            "label": f"RSI ≤ {config['max_rsi_buy']} (não sobrecomprado)",
            "ok": rsi <= config["max_rsi_buy"],
            "value": f"{rsi:.1f}",
        },
        {
            "label": f"ADX ≥ {config['min_adx']} (tendência presente)",
            "ok": adx >= config["min_adx"],
            "value": f"{adx:.1f}",
        },
        {
            "label": f"Volume ratio ≥ {config['min_volume_ratio']} (pressão compradora)",
            "ok": volume_ratio >= config["min_volume_ratio"],
            "value": f"{volume_ratio:.2f}x",
        },
        {
            "label": "MACD positivo ou histograma positivo",
            "ok": macd > macd_signal or macd_hist > 0,
            "value": f"hist {macd_hist:+.4f}",
        },
        {
            "label": "Tendência de alta (preço ou MA5 acima de MA20)",
            "ok": close > ma_5 or ma_5 > ma_20,
            "value": f"MA5>{ma_20:.2f}" if ma_5 > ma_20 else f"P>{ma_5:.2f}",
        },
        {
            "label": "BB position < 0.85 (não no topo da banda)",
            "ok": bb_position < 0.85,
            "value": f"{bb_position:.2f}",
        },
    ]

    buy_obg_ok  = sum(1 for c in buy_conditions[:2] if c["ok"])
    buy_sec_ok  = sum(1 for c in buy_conditions[2:] if c["ok"])
    buy_ready   = buy_obg_ok == 2 and buy_sec_ok >= 3

    # ── avaliar condições de VENDA ────────────────────────────────────────────
    stop_hit        = posicao_aberta and lucro_pct <= -config["stop_loss_pct"]
    tp_ajustado     = config["take_profit_pct"] * 1.5
    take_profit_hit = posicao_aberta and lucro_pct >= tp_ajustado

    sell_conditions = [
        {
            "label": f"Stop Loss ≤ -{config['stop_loss_pct']:.0%}",
            "ok": stop_hit,
            "value": f"{lucro_pct:.2%}" if posicao_aberta else "—",
            "urgent": stop_hit,
        },
        {
            "label": f"Take Profit ≥ +{tp_ajustado:.0%}",
            "ok": take_profit_hit,
            "value": f"{lucro_pct:.2%}" if posicao_aberta else "—",
        },
        {
            "label": f"Modelo prevê queda + baixa confiança (< {config['min_confidence_sell']:.0%})",
            "ok": sinal_atual == "sell" and confianca < config["min_confidence_sell"],
            "value": f"{confianca:.1%}",
        },
        {
            "label": f"RSI ≥ {config['max_rsi_sell']} (muito sobrecomprado)",
            "ok": rsi >= config["max_rsi_sell"],
            "value": f"{rsi:.1f}",
        },
        {
            "label": "MACD negativo E histograma negativo",
            "ok": macd < macd_signal and macd_hist < 0,
            "value": f"hist {macd_hist:+.4f}",
        },
        {
            "label": "Preço abaixo de MA5 e MA5 abaixo de MA20",
            "ok": close < ma_5 and ma_5 < ma_20,
            "value": f"P={close:.2f}",
        },
        {
            "label": "BB position > 0.90 (no topo da banda)",
            "ok": bb_position > 0.90,
            "value": f"{bb_position:.2f}",
        },
        {
            "label": "Volume ratio < 0.8 (fraqueza de volume)",
            "ok": volume_ratio < 0.8,
            "value": f"{volume_ratio:.2f}x",
        },
    ]

    reversao_clara = macd < macd_signal and close < ma_5 and rsi > 70
    sell_technical = sum(1 for c in sell_conditions[2:] if c["ok"])
    sell_ready     = stop_hit or take_profit_hit or sell_technical >= 4 or reversao_clara

    # ── helpers para serialização ─────────────────────────────────────────────
    def cond_js(conds):
        items = []
        for c in conds:
            ok      = "true" if c["ok"] else "false"
            urgent  = "true" if c.get("urgent") else "false"
            label   = c["label"].replace('"', "'").replace("\n", " ")
            value   = c["value"].replace('"', "'")
            items.append(f'{{label:"{label}",ok:{ok},urgent:{urgent},value:"{value}"}}')
        return "[" + ",".join(items) + "]"

    sinal_color = {
        "buy":  "#00e676",
        "sell": "#ff5252",
        "hold": "#ffd740",
    }.get(sinal_atual, "#ffd740")

    sinal_label = {
        "buy":  "COMPRA",
        "sell": "VENDA",
        "hold": "AGUARDANDO",
    }.get(sinal_atual, "AGUARDANDO")

    conf_pct    = int(confianca * 100)
    lucro_fmt   = f"{lucro_pct:+.2%}" if posicao_aberta and preco_compra else "—"
    lucro_color = "#00e676" if lucro_pct >= 0 else "#ff5252"
    pos_label   = "ABERTA" if posicao_aberta else "FECHADA"
    pos_color   = "#00e676" if posicao_aberta else "#546e7a"

    buy_js  = cond_js(buy_conditions)
    sell_js = cond_js(sell_conditions)

    html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;600&display=swap');

  *{{ box-sizing:border-box; margin:0; padding:0; }}

  body{{
    font-family:'DM Sans',sans-serif;
    background:#0b0f1a;
    color:#e0e6f0;
    padding:12px;
    font-size:13px;
  }}

  .panel{{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:12px;
  }}

  /* top status bar */
  .status-bar{{
    grid-column:1/-1;
    display:flex;
    align-items:center;
    gap:16px;
    background:#111827;
    border:1px solid #1e2d3d;
    border-radius:10px;
    padding:10px 16px;
  }}
  .signal-badge{{
    font-family:'Space Mono',monospace;
    font-size:15px;
    font-weight:700;
    letter-spacing:.12em;
    padding:4px 14px;
    border-radius:6px;
    background:{sinal_color}22;
    color:{sinal_color};
    border:1px solid {sinal_color}55;
  }}
  .stat{{
    display:flex; flex-direction:column; gap:2px;
  }}
  .stat-label{{
    font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:#546e7a;
  }}
  .stat-value{{
    font-family:'Space Mono',monospace; font-size:13px; font-weight:700; color:#cfd8dc;
  }}
  .conf-bar-wrap{{
    flex:1;
    display:flex; flex-direction:column; gap:4px;
  }}
  .conf-bar-bg{{
    height:6px; background:#1e2d3d; border-radius:3px; overflow:hidden;
  }}
  .conf-bar-fill{{
    height:100%; border-radius:3px;
    background:linear-gradient(90deg,#1565c0,#42a5f5);
    transition:width .4s ease;
    width:{conf_pct}%;
  }}

  /* card */
  .card{{
    background:#111827;
    border:1px solid #1e2d3d;
    border-radius:10px;
    padding:12px;
    display:flex; flex-direction:column; gap:8px;
  }}
  .card-header{{
    display:flex; align-items:center; justify-content:space-between;
    margin-bottom:2px;
  }}
  .card-title{{
    font-family:'Space Mono',monospace;
    font-size:11px; letter-spacing:.1em; text-transform:uppercase;
    color:#78909c;
  }}
  .badge{{
    font-family:'Space Mono',monospace;
    font-size:10px; font-weight:700; letter-spacing:.06em;
    padding:2px 8px; border-radius:4px;
  }}
  .badge-ready{{ background:#00e67622; color:#00e676; border:1px solid #00e67655; }}
  .badge-wait{{ background:#ffd74022; color:#ffd740; border:1px solid #ffd74055; }}
  .badge-sell{{ background:#ff525222; color:#ff5252; border:1px solid #ff525255; }}
  .badge-info{{ background:#42a5f522; color:#42a5f5; border:1px solid #42a5f555; }}

  /* progress ring (buy side) */
  .progress-summary{{
    display:flex; align-items:center; gap:10px; padding:6px 0;
    border-bottom:1px solid #1e2d3d; margin-bottom:2px;
  }}
  .ring-wrap{{ position:relative; width:44px; height:44px; flex-shrink:0; }}
  .ring-wrap svg{{ transform:rotate(-90deg); }}
  .ring-bg{{ fill:none; stroke:#1e2d3d; stroke-width:4; }}
  .ring-fg{{ fill:none; stroke-width:4; stroke-linecap:round; transition:stroke-dashoffset .5s ease; }}
  .ring-label{{
    position:absolute; inset:0;
    display:flex; align-items:center; justify-content:center;
    font-family:'Space Mono',monospace; font-size:11px; font-weight:700;
  }}
  .summary-text{{ font-size:12px; color:#90a4ae; line-height:1.5; }}
  .summary-text strong{{ color:#cfd8dc; }}

  /* condition rows */
  .cond-row{{
    display:flex; align-items:center; gap:8px;
    padding:5px 8px;
    border-radius:6px;
    background:#0d1421;
    border:1px solid transparent;
    transition:border-color .2s;
  }}
  .cond-row.ok{{ border-color:#00e67633; }}
  .cond-row.urgent{{ border-color:#ff525266; background:#1a0d0d; }}
  .cond-icon{{ font-size:14px; flex-shrink:0; width:18px; text-align:center; }}
  .cond-text{{ flex:1; font-size:12px; color:#90a4ae; line-height:1.3; }}
  .cond-row.ok .cond-text{{ color:#b0bec5; }}
  .cond-value{{
    font-family:'Space Mono',monospace; font-size:11px;
    color:#546e7a; flex-shrink:0;
  }}
  .cond-row.ok .cond-value{{ color:#42a5f5; }}
  .cond-row.urgent .cond-value{{ color:#ff5252; }}

  /* separator label */
  .sep{{ font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:#37474f;
         padding:2px 0 0; }}
</style>
</head>
<body>

<div class="panel" id="panel">

  <!-- STATUS BAR -->
  <div class="status-bar">
    <div class="signal-badge" id="sigBadge">{sinal_label}</div>
    <div class="stat">
      <span class="stat-label">Posição</span>
      <span class="stat-value" style="color:{pos_color}">{pos_label}</span>
    </div>
    <div class="stat">
      <span class="stat-label">P&L</span>
      <span class="stat-value" style="color:{lucro_color}">{lucro_fmt}</span>
    </div>
    <div class="stat">
      <span class="stat-label">RSI</span>
      <span class="stat-value">{rsi:.1f}</span>
    </div>
    <div class="stat">
      <span class="stat-label">ADX</span>
      <span class="stat-value">{adx:.1f}</span>
    </div>
    <div class="conf-bar-wrap">
      <div class="stat-label">Confiança do Modelo — {conf_pct}%</div>
      <div class="conf-bar-bg"><div class="conf-bar-fill"></div></div>
    </div>
  </div>

  <!-- BUY CARD -->
  <div class="card" id="buyCard">
    <div class="card-header">
      <span class="card-title">Condições de Compra</span>
      <span class="badge" id="buyBadge">...</span>
    </div>
    <div class="progress-summary" id="buySummary">
      <div class="ring-wrap">
        <svg viewBox="0 0 44 44" width="44" height="44">
          <circle class="ring-bg" cx="22" cy="22" r="18"/>
          <circle class="ring-fg" id="buyRing" cx="22" cy="22" r="18"
            stroke="#00e676"
            stroke-dasharray="113.1"
            stroke-dashoffset="113.1"/>
        </svg>
        <div class="ring-label" id="buyRingLabel" style="color:#00e676">0</div>
      </div>
      <div class="summary-text" id="buySummaryText">
        Aguardando dados...
      </div>
    </div>
    <div id="buyList"></div>
  </div>

  <!-- SELL CARD -->
  <div class="card" id="sellCard">
    <div class="card-header">
      <span class="card-title">Condições de Venda</span>
      <span class="badge" id="sellBadge">...</span>
    </div>
    <div class="progress-summary" id="sellSummary">
      <div class="ring-wrap">
        <svg viewBox="0 0 44 44" width="44" height="44">
          <circle class="ring-bg" cx="22" cy="22" r="18"/>
          <circle class="ring-fg" id="sellRing" cx="22" cy="22" r="18"
            stroke="#ff5252"
            stroke-dasharray="113.1"
            stroke-dashoffset="113.1"/>
        </svg>
        <div class="ring-label" id="sellRingLabel" style="color:#ff5252">0</div>
      </div>
      <div class="summary-text" id="sellSummaryText">
        Aguardando dados...
      </div>
    </div>
    <div id="sellList"></div>
  </div>

</div>

<script>
const buyConds  = {buy_js};
const sellConds = {sell_js};

const buyObgOk  = buyConds.slice(0,2).filter(c=>c.ok).length;
const buySecOk  = buyConds.slice(2).filter(c=>c.ok).length;
const buyReady  = buyObgOk===2 && buySecOk>=3;

const stopHit   = sellConds[0].ok;
const tpHit     = sellConds[1].ok;
const sellTech  = sellConds.slice(2).filter(c=>c.ok).length;
const sellReady = stopHit || tpHit || sellTech >= 4;

// ── render condition list ──────────────────────────────────
function renderList(conds, containerId, sep) {{
  const el = document.getElementById(containerId);
  let html = '';
  conds.forEach((c,i) => {{
    if(sep && i===sep) html += `<div class="sep">↓ Stop / TP</div>`;
    const cls = c.urgent ? 'urgent' : (c.ok ? 'ok' : '');
    const icon = c.urgent ? '⚠️' : (c.ok ? '✅' : '⬜');
    html += `<div class="cond-row ${{cls}}">
      <span class="cond-icon">${{icon}}</span>
      <span class="cond-text">${{c.label}}</span>
      <span class="cond-value">${{c.value}}</span>
    </div>`;
  }});
  el.innerHTML = html;
}}

// ── ring progress ──────────────────────────────────────────
function setRing(ringId, labelId, value, total, color) {{
  const circumference = 113.1;
  const offset = circumference - (value / total) * circumference;
  const ring = document.getElementById(ringId);
  const label = document.getElementById(labelId);
  ring.style.stroke = color;
  ring.style.strokeDashoffset = offset;
  label.textContent = value + '/' + total;
  label.style.color = color;
}}

// ── buy ───────────────────────────────────────────────────
renderList(buyConds, 'buyList');
const buyTotal = buyConds.slice(2).length;
setRing('buyRing','buyRingLabel', buySecOk, buyTotal, buyReady ? '#00e676' : '#ffd740');

const buyBadge = document.getElementById('buyBadge');
const buySummaryText = document.getElementById('buySummaryText');
if(buyReady){{
  buyBadge.className = 'badge badge-ready';
  buyBadge.textContent = 'PRONTO';
  buySummaryText.innerHTML = `<strong>✅ Sinal de Compra Gerado</strong><br>Obrigatórias: ${{buyObgOk}}/2 · Secundárias: ${{buySecOk}}/${{buyTotal}} (mín. 3)`;
}} else {{
  const faltam = 3 - buySecOk;
  buyBadge.className = 'badge badge-wait';
  buyBadge.textContent = 'AGUARDANDO';
  buySummaryText.innerHTML = `Obrigatórias: <strong>${{buyObgOk}}/2</strong> · Secundárias: <strong>${{buySecOk}}/${{buyTotal}}</strong><br>Faltam <strong>${{Math.max(0,2-buyObgOk)}} obrigatória(s)</strong> e <strong>${{Math.max(0,faltam)}} secundária(s)</strong>`;
}}

// ── sell ──────────────────────────────────────────────────
renderList(sellConds, 'sellList', 2);
const sellTotal = sellConds.slice(2).length;
setRing('sellRing','sellRingLabel', sellTech, sellTotal, sellReady ? '#ff5252' : '#546e7a');

const sellBadge = document.getElementById('sellBadge');
const sellSummaryText = document.getElementById('sellSummaryText');
if(stopHit){{
  sellBadge.className = 'badge badge-sell';
  sellBadge.textContent = '⚠ STOP';
  sellSummaryText.innerHTML = `<strong style="color:#ff5252">Stop Loss atingido!</strong><br>Sinal de venda imediata`;
}} else if(tpHit){{
  sellBadge.className = 'badge badge-sell';
  sellBadge.textContent = ' TAKE PROFIT';
  sellSummaryText.innerHTML = `<strong style="color:#00e676">Take Profit atingido!</strong><br>Sinal de venda com lucro`;
}} else if(sellReady){{
  sellBadge.className = 'badge badge-sell';
  sellBadge.textContent = 'VENDER';
  sellSummaryText.innerHTML = `<strong>Sinal Técnico de Venda</strong><br>Condições: <strong>${{sellTech}}/${{sellTotal}}</strong> (mín. 4)`;
}} else {{
  sellBadge.className = 'badge badge-info';
  sellBadge.textContent = 'SEGURANDO';
  sellSummaryText.innerHTML = `Sem sinais de reversão no momento<br>Técnicas ativas: <strong>${{sellTech}}/${{sellTotal}}</strong> (mín. 4)`;
}}
</script>
</body>
</html>
"""

    components.html(html, height=height, scrolling=False)


# ─────────────────────────────────────────────────────────────────────────────
# Integração sugerida para main_app.py
# ─────────────────────────────────────────────────────────────────────────────
# Localize a seção "### Indicadores Atuais" (~linha 925) e substitua/adicione:
#
#   try:
#       from strategies.features import gerar_features_melhorada
#       from signal_preview_panel import render_signal_panel
#
#       indicadores_df = gerar_features_melhorada(df)
#       ultimo = indicadores_df.iloc[-1].to_dict()
#
#       resultado = executar_estrategia_ai_melhorada(
#           df,
#           posicao_aberta=st.session_state.bot_data.get('posicao_aberta', False),
#           preco_compra=st.session_state.bot_data.get('preco_compra'),
#       )
#
#       st.markdown("###  Preview de Sinais")
#       render_signal_panel(
#           indicadores=ultimo,
#           posicao_aberta=st.session_state.bot_data.get('posicao_aberta', False),
#           preco_compra=st.session_state.bot_data.get('preco_compra'),
#           confianca=resultado.get('confianca', 0.0),
#           sinal_atual=resultado.get('sinal', 'hold'),
#       )
#   except Exception as e:
#       logger.warning("Erro ao renderizar painel de sinais: %s", e)
#