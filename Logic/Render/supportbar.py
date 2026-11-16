from html import escape
from UI.Config.supportLevel import SUPPORT_LEVELS



def render_support_bar_html(level: str, text_color: str, border_color: str, accent_color: str) -> str:
    cfg = SUPPORT_LEVELS.get(level.lower(), {"pct": 0, "color": accent_color, "label": level.title()})
    return f"""
    <div style="margin:14px 0 10px 0;">
      <div style="display:flex;justify-content:space-between;margin-bottom:7px;
                  font-size:11px;font-weight:700;color:{accent_color};
                  letter-spacing:.6px;text-transform:uppercase;opacity:.95;">
        <span>Evidence Support Level</span>
        <span style="color:{accent_color};">{escape("" if cfg['label'] is None else str(cfg['label']))}</span>
      </div>
      <div style="width:100%;height:5px;background:{border_color};
                  border-radius:999px;overflow:hidden;">
        <div style="width:{cfg['pct']}%;height:100%;background:{accent_color};
                    border-radius:999px;"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:5px;
                  font-size:10px;color:{text_color};opacity:.45;">
        <span>None</span><span>Limited</span><span>Indirect</span><span>Moderate</span><span>Direct</span>
      </div>
    </div>
    """
