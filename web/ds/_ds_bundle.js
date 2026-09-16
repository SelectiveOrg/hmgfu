/* @ds-bundle: {"format":4,"namespace":"PersonalAgentDesignSystem_94ad89","components":[{"name":"Badge","sourcePath":"components/Badge/Badge.jsx"},{"name":"Button","sourcePath":"components/Button/Button.jsx"},{"name":"CanvasWidget","sourcePath":"components/CanvasWidget/CanvasWidget.jsx"},{"name":"Card","sourcePath":"components/Card/Card.jsx"},{"name":"DiffView","sourcePath":"components/DiffView/DiffView.jsx"},{"name":"HmgGraph","sourcePath":"components/HmgGraph/HmgGraph.jsx"},{"name":"HmgHexGrid","sourcePath":"components/HmgHexGrid/HmgHexGrid.jsx"},{"name":"IconButton","sourcePath":"components/IconButton/IconButton.jsx"},{"name":"Input","sourcePath":"components/Input/Input.jsx"},{"name":"MessageBubble","sourcePath":"components/MessageBubble/MessageBubble.jsx"},{"name":"Pill","sourcePath":"components/Pill/Pill.jsx"},{"name":"PlanTracker","sourcePath":"components/PlanTracker/PlanTracker.jsx"},{"name":"ProviderSelect","sourcePath":"components/ProviderSelect/ProviderSelect.jsx"},{"name":"SessionRow","sourcePath":"components/SessionRow/SessionRow.jsx"},{"name":"ToolCallBlock","sourcePath":"components/ToolCallBlock/ToolCallBlock.jsx"},{"name":"WidgetCard","sourcePath":"components/WidgetCard/WidgetCard.jsx"}],"sourceHashes":{"assets/pa-ui.js":"d0852f41d2c9","components/Badge/Badge.jsx":"94d19ac501d6","components/Button/Button.jsx":"cc4790a28d8a","components/CanvasWidget/CanvasWidget.jsx":"be8c2794458b","components/Card/Card.jsx":"8863ef11287a","components/DiffView/DiffView.jsx":"1c4148148f6a","components/HmgGraph/HmgGraph.jsx":"f1884fa44f0d","components/HmgHexGrid/HmgHexGrid.jsx":"89dbd3bd450c","components/IconButton/IconButton.jsx":"011864c61375","components/Input/Input.jsx":"676513fa0794","components/MessageBubble/MessageBubble.jsx":"3447b2b707b0","components/Pill/Pill.jsx":"ad77fb430164","components/PlanTracker/PlanTracker.jsx":"e5d99b2f9cd7","components/ProviderSelect/ProviderSelect.jsx":"7bdd839ff5b8","components/SessionRow/SessionRow.jsx":"d415a9b7a1d9","components/ToolCallBlock/ToolCallBlock.jsx":"ffb108ad034e","components/WidgetCard/WidgetCard.jsx":"5151f0f3ae7e","ui_kits/cowork/Canvas.jsx":"a3ffd7544890","ui_kits/cowork/CoworkApp.jsx":"6c8fe4a0de38","ui_kits/cowork/Rail.jsx":"a37beecabcaf","ui_kits/cowork/Settings.jsx":"95705ecbb27f","ui_kits/cowork/Transcript.jsx":"b74f16aeee7d","ui_kits/personal-agent/App.jsx":"745f1c80d3f6","ui_kits/personal-agent/Chat.jsx":"cb8ef2d0eaef","ui_kits/personal-agent/Login.jsx":"d719d49667cd","ui_kits/personal-agent/RightPanel.jsx":"570be2c772a6","ui_kits/personal-agent/Sidebar.jsx":"3476eea4b2fe"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.PersonalAgentDesignSystem_94ad89 = window.PersonalAgentDesignSystem_94ad89 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// assets/pa-ui.js
try { (() => {
/* Personal Agent — shared browser helper for @dsCard demos & UI kits.
   Loads AFTER React (uses React global) and AFTER the lucide UMD bundle.
   Exposes window.PA.Icon — renders a lucide glyph as an inline SVG React element,
   matching the app's icon system (lucide-react, ~2px stroke, round caps).

   Handles every lucide UMD data shape robustly:
     • a single IconNode  ["svg", attrs, [childNodes]]
     • a bare svg-child list  [["path",{}], ["rect",{}], ...]
     • a single shape node  ["path", {}]
   and never throws (returns null when a glyph is missing) so a bad name can't
   unmount the host app. */
(function () {
  var R = window.React;
  function toPascal(name) {
    return String(name).replace(/(^|-)([a-z])/g, function (_, __, c) {
      return c.toUpperCase();
    });
  }
  // Recursively render an IconNode [tag, attrs, children] → React element.
  function renderNode(node, key) {
    if (!Array.isArray(node)) return null;
    var tag = node[0],
      attrs = node[1] || {},
      children = node[2];
    if (typeof tag !== "string") return null;
    var kids = Array.isArray(children) ? children.map(function (c, i) {
      return renderNode(c, i);
    }) : null;
    return R.createElement(tag, Object.assign({
      key: key
    }, attrs), kids);
  }
  function Icon(props) {
    props = props || {};
    var name = props.name,
      size = props.size || 16,
      stroke = props.stroke || 2;
    var color = props.color || "currentColor",
      style = props.style,
      className = props.className;
    var lib = window.lucide || {};
    var data = lib[name] || lib[toPascal(name)] || lib.icons && (lib.icons[name] || lib.icons[toPascal(name)]);
    if (!data || !R || !Array.isArray(data)) return null;

    // Determine the list of shape child-nodes to draw inside our <svg>.
    var shapes;
    if (typeof data[0] === "string") {
      // single IconNode
      if (data[0] === "svg") shapes = Array.isArray(data[2]) ? data[2] : [];else shapes = [data]; // a lone shape like ["path", {...}]
    } else {
      shapes = data; // already a list of shape nodes
    }
    var children = shapes.map(function (n, i) {
      return renderNode(n, i);
    }).filter(Boolean);
    return R.createElement("svg", {
      width: size,
      height: size,
      viewBox: "0 0 24 24",
      fill: "none",
      stroke: color,
      strokeWidth: stroke,
      strokeLinecap: "round",
      strokeLinejoin: "round",
      className: className,
      style: Object.assign({
        display: "inline-block",
        flexShrink: 0
      }, style)
    }, children);
  }
  window.PA = window.PA || {};
  window.PA.Icon = Icon;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "assets/pa-ui.js", error: String((e && e.message) || e) }); }

// components/Badge/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Badge — small labelled tag. Two shapes the app uses: a soft "provider"
 * capsule (rounded-full, teal-tinted, e.g. `codex · gpt-5`) and an uppercase
 * outline tag (rounded-full, tracked caps, e.g. AUTONOMY / BACKGROUND ENABLED).
 */
function Badge({
  variant = "soft",
  tone = "primary",
  uppercase = false,
  children,
  style,
  ...rest
}) {
  const tones = {
    primary: {
      fg: "hsl(var(--primary))",
      ring: "hsl(var(--primary) / 0.2)",
      fill: "hsl(var(--primary) / 0.1)"
    },
    emerald: {
      fg: "hsl(158 64% 62%)",
      ring: "hsl(158 64% 45% / 0.3)",
      fill: "hsl(158 64% 45% / 0.1)"
    },
    neutral: {
      fg: "hsl(var(--muted-foreground))",
      ring: "hsl(var(--border))",
      fill: "hsl(var(--surface-2))"
    },
    danger: {
      fg: "hsl(var(--destructive))",
      ring: "hsl(var(--destructive) / 0.3)",
      fill: "hsl(var(--destructive) / 0.1)"
    }
  };
  const t = tones[tone] || tones.primary;
  const shape = variant === "outline" ? {
    background: t.fill,
    border: `1px solid ${t.ring}`,
    fontSize: 9,
    fontWeight: 600,
    padding: "2px 8px"
  } : {
    background: t.fill,
    border: `1px solid ${t.ring}`,
    fontSize: 10,
    fontWeight: 500,
    padding: "2px 8px"
  };
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 4,
      borderRadius: "var(--radius-full)",
      color: t.fg,
      fontFamily: "var(--font-sans)",
      textTransform: uppercase ? "uppercase" : "none",
      letterSpacing: uppercase ? "0.05em" : "0",
      whiteSpace: "nowrap",
      ...shape,
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/Badge/Badge.jsx", error: String((e && e.message) || e) }); }

// components/Button/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Button — the app's primary action control (shadcn button, exact variants).
 * Radius 10px (md), height 40/36/44px, font 14px medium, teal primary.
 */
function Button({
  variant = "default",
  size = "default",
  disabled = false,
  type = "button",
  leftIcon,
  rightIcon,
  children,
  style,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const [active, setActive] = React.useState(false);
  const sizes = {
    sm: {
      height: 36,
      padding: "0 12px",
      fontSize: 14,
      radius: "var(--radius-md)"
    },
    default: {
      height: 40,
      padding: "0 16px",
      fontSize: 14,
      radius: "var(--radius-md)"
    },
    lg: {
      height: 44,
      padding: "0 32px",
      fontSize: 14,
      radius: "var(--radius-md)"
    },
    icon: {
      height: 40,
      width: 40,
      padding: 0,
      fontSize: 14,
      radius: "var(--radius-md)"
    }
  };
  const s = sizes[size] || sizes.default;
  const variants = {
    default: {
      base: {
        background: "hsl(var(--primary))",
        color: "hsl(var(--primary-foreground))",
        border: "1px solid transparent"
      },
      hover: {
        background: "hsl(var(--primary) / 0.9)"
      }
    },
    destructive: {
      base: {
        background: "hsl(var(--destructive))",
        color: "hsl(var(--destructive-foreground))",
        border: "1px solid transparent"
      },
      hover: {
        background: "hsl(var(--destructive) / 0.9)"
      }
    },
    outline: {
      base: {
        background: "hsl(var(--background))",
        color: "hsl(var(--foreground))",
        border: "1px solid hsl(var(--input))"
      },
      hover: {
        background: "hsl(var(--surface-hover))",
        color: "hsl(var(--foreground))"
      }
    },
    secondary: {
      base: {
        background: "hsl(var(--secondary))",
        color: "hsl(var(--secondary-foreground))",
        border: "1px solid transparent"
      },
      hover: {
        background: "hsl(var(--secondary) / 0.8)"
      }
    },
    ghost: {
      base: {
        background: "transparent",
        color: "hsl(var(--muted-foreground))",
        border: "1px solid transparent"
      },
      hover: {
        background: "hsl(var(--surface-hover))",
        color: "hsl(var(--foreground))"
      }
    },
    link: {
      base: {
        background: "transparent",
        color: "hsl(var(--primary))",
        border: "1px solid transparent",
        textDecoration: hover ? "underline" : "none",
        textUnderlineOffset: 4
      },
      hover: {}
    }
  };
  const v = variants[variant] || variants.default;
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    disabled: disabled,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => {
      setHover(false);
      setActive(false);
    },
    onMouseDown: () => setActive(true),
    onMouseUp: () => setActive(false),
    style: {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      whiteSpace: "nowrap",
      fontFamily: "var(--font-sans)",
      fontWeight: 500,
      height: s.height,
      width: s.width,
      padding: s.padding,
      fontSize: s.fontSize,
      borderRadius: s.radius,
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1,
      transition: "background var(--dur-fast), color var(--dur-fast), transform var(--dur-fast)",
      transform: active && !disabled ? "translateY(0.5px)" : "none",
      ...v.base,
      ...(hover && !disabled ? v.hover : null),
      ...style
    }
  }, rest), leftIcon, children, rightIcon);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/Button/Button.jsx", error: String((e && e.message) || e) }); }

// components/CanvasWidget/CanvasWidget.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * CanvasWidget — a tile on the agent's widget canvas (AG-UI style). Draggable
 * card with a grip + title header, an optional "agent" badge for widgets the
 * model generated on the fly, hover controls (expand / refresh / close) and a
 * resize corner. The host wires actual drag/resize by passing `dragHandleProps`
 * (onto the grip) and `resizeHandleProps` (onto the corner); `fill` makes the
 * card fill a sized wrapper and scroll its body.
 */
function CanvasWidget({
  title,
  icon,
  generated = false,
  accent,
  onClose,
  onRefresh,
  onExpand,
  expanded = false,
  fill = false,
  dragHandleProps,
  resizeHandleProps,
  footer,
  children,
  style,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const edge = accent || (generated ? "hsl(var(--primary))" : "hsl(var(--border))");
  const ctrl = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    height: 22,
    width: 22,
    borderRadius: "var(--radius-sm)",
    border: "none",
    background: "transparent",
    color: "hsl(var(--muted-foreground))",
    cursor: "pointer",
    fontSize: 12,
    transition: "color var(--dur-fast), background var(--dur-fast)"
  };
  return /*#__PURE__*/React.createElement("div", _extends({
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      position: "relative",
      display: "flex",
      flexDirection: "column",
      height: fill ? "100%" : undefined,
      boxSizing: "border-box",
      borderRadius: "var(--radius-lg)",
      border: "1px solid hsl(var(--border))",
      borderTop: `2px solid ${edge}`,
      background: "hsl(var(--surface-2))",
      boxShadow: hover ? "var(--shadow-md)" : "var(--shadow-sm)",
      overflow: "hidden",
      transition: "box-shadow var(--dur-fast)",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 7,
      padding: "7px 9px",
      borderBottom: "1px solid hsl(var(--border))",
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("span", _extends({}, dragHandleProps || {}, {
    style: {
      color: "hsl(var(--muted-foreground))",
      cursor: dragHandleProps ? "grab" : "default",
      fontSize: 12,
      lineHeight: 1,
      letterSpacing: "-1px",
      userSelect: "none",
      touchAction: "none"
    },
    title: "Drag"
  }), "\u283F"), icon && /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      color: generated ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))"
    }
  }, icon), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      fontSize: 12,
      fontWeight: 600,
      color: "hsl(var(--foreground))",
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
    }
  }, title), generated && /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 3,
      fontSize: 9,
      fontWeight: 600,
      textTransform: "uppercase",
      letterSpacing: "0.05em",
      color: "hsl(var(--primary))",
      background: "hsl(var(--primary) / 0.12)",
      border: "1px solid hsl(var(--primary) / 0.25)",
      borderRadius: "var(--radius-full)",
      padding: "1px 6px"
    }
  }, "\u2726 agent"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 1,
      opacity: hover ? 1 : 0,
      transition: "opacity var(--dur-fast)"
    }
  }, onExpand && /*#__PURE__*/React.createElement("button", {
    style: ctrl,
    onClick: onExpand,
    title: expanded ? "Restore" : "Expand"
  }, expanded ? "⤡" : "⤢"), onRefresh && /*#__PURE__*/React.createElement("button", {
    style: ctrl,
    onClick: onRefresh,
    title: "Refresh"
  }, "\u21BB"), onClose && /*#__PURE__*/React.createElement("button", {
    style: ctrl,
    onClick: onClose,
    title: "Remove"
  }, "\u2715"))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: fill ? 1 : undefined,
      minHeight: 0,
      overflow: fill ? "auto" : undefined
    }
  }, children), footer && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "6px 10px",
      borderTop: "1px solid hsl(var(--border))",
      fontSize: 11,
      color: "hsl(var(--muted-foreground))",
      flexShrink: 0
    }
  }, footer), /*#__PURE__*/React.createElement("span", _extends({}, resizeHandleProps || {}, {
    style: {
      position: "absolute",
      right: 2,
      bottom: 2,
      width: 14,
      height: 14,
      borderRight: "2px solid hsl(var(--muted-foreground) / 0.55)",
      borderBottom: "2px solid hsl(var(--muted-foreground) / 0.55)",
      opacity: resizeHandleProps ? hover ? 0.9 : 0.35 : hover ? 0.6 : 0,
      cursor: resizeHandleProps ? "nwse-resize" : "default",
      pointerEvents: resizeHandleProps ? "auto" : "none",
      touchAction: "none",
      transition: "opacity var(--dur-fast)"
    }
  })));
}
Object.assign(__ds_scope, { CanvasWidget });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/CanvasWidget/CanvasWidget.jsx", error: String((e && e.message) || e) }); }

// components/Card/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Card — the app's base container: rounded-lg, 1px border, dark fill.
 * `surface` picks the elevation: "flush" (background) for cards sitting on a
 * raised panel, "raised" (surface-2) for cards on the page.
 */
function Card({
  surface = "raised",
  padded = false,
  hover = false,
  children,
  style,
  ...rest
}) {
  const [isHover, setIsHover] = React.useState(false);
  const bg = surface === "flush" ? "hsl(var(--background))" : "hsl(var(--surface-2))";
  return /*#__PURE__*/React.createElement("div", _extends({
    onMouseEnter: () => hover && setIsHover(true),
    onMouseLeave: () => hover && setIsHover(false),
    style: {
      borderRadius: "var(--radius-lg)",
      border: "1px solid hsl(var(--border))",
      background: isHover ? "hsl(var(--surface-hover))" : bg,
      overflow: "hidden",
      transition: "background var(--dur-fast), border-color var(--dur-fast)",
      padding: padded ? 12 : 0,
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/Card/Card.jsx", error: String((e && e.message) || e) }); }

// components/DiffView/DiffView.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Parse a unified-diff-ish string into typed lines. Lines starting with + / -
   are add/del; everything else is context. A line starting with "@@" is a hunk. */
function parseDiff(text) {
  return String(text).split("\n").map(l => {
    if (l.startsWith("@@")) return {
      type: "hunk",
      text: l
    };
    if (l.startsWith("+")) return {
      type: "add",
      text: l.slice(1)
    };
    if (l.startsWith("-")) return {
      type: "del",
      text: l.slice(1)
    };
    return {
      type: "ctx",
      text: l.replace(/^ /, "")
    };
  });
}

/**
 * DiffView — a file diff viewer. Header shows the filename with +N / −M counts;
 * the body renders unified-diff lines with add (green) / del (red) gutters using
 * the theme's diff tints. Pass a `diff` string (unified) or explicit `lines`.
 */
function DiffView({
  filename,
  diff,
  lines,
  added,
  removed,
  style,
  ...rest
}) {
  const parsed = lines || (diff ? parseDiff(diff) : []);
  const adds = added != null ? added : parsed.filter(l => l.type === "add").length;
  const dels = removed != null ? removed : parsed.filter(l => l.type === "del").length;
  const bg = {
    add: "hsl(var(--diff-add-bg))",
    del: "hsl(var(--diff-del-bg))",
    hunk: "hsl(var(--surface-3))",
    ctx: "transparent"
  };
  const fg = {
    add: "hsl(var(--diff-add-fg))",
    del: "hsl(var(--diff-del-fg))",
    hunk: "hsl(var(--muted-foreground))",
    ctx: "hsl(var(--foreground))"
  };
  const sign = {
    add: "+",
    del: "−",
    hunk: " ",
    ctx: " "
  };
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      borderRadius: "var(--radius-md)",
      border: "1px solid hsl(var(--border))",
      background: "hsl(var(--surface-2))",
      overflow: "hidden",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      padding: "7px 12px",
      borderBottom: "1px solid hsl(var(--border))"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      color: "hsl(var(--foreground))",
      flex: 1,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
    }
  }, filename), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 11,
      color: "hsl(var(--diff-add-fg))"
    }
  }, "+", adds), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 11,
      color: "hsl(var(--diff-del-fg))"
    }
  }, "\u2212", dels)), /*#__PURE__*/React.createElement("div", {
    style: {
      overflow: "auto",
      maxHeight: 320
    }
  }, parsed.map((l, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: "flex",
      background: bg[l.type],
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      lineHeight: "18px"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 16,
      textAlign: "center",
      color: fg[l.type],
      opacity: 0.7,
      flexShrink: 0,
      userSelect: "none"
    }
  }, sign[l.type]), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      whiteSpace: "pre-wrap",
      wordBreak: "break-word",
      color: fg[l.type],
      paddingRight: 10,
      fontWeight: l.type === "hunk" ? 600 : 400
    }
  }, l.text || "\u00a0")))));
}
Object.assign(__ds_scope, { DiffView });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/DiffView/DiffView.jsx", error: String((e && e.message) || e) }); }

// components/HmgGraph/HmgGraph.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* ── HMG palette (exact values from the app's MemoryGraphWidget) ───────────── */
const BIOME = {
  A: "#2DD4BF",
  B: "#FF6B6B",
  C: "#8892B0"
}; // Positive / Negative / Neutral
const TYPE_COLOR = {
  macro: "#22D3EE",
  event: "#F59E0B"
};
const EDGE = {
  Wormhole: "rgba(167,139,250,0.60)",
  Turn_Response: "rgba(136,146,176,0.14)"
};
function nodeColor(n) {
  if (n.type === "macro") return TYPE_COLOR.macro;
  if (n.type === "event") return TYPE_COLOR.event;
  return BIOME[n.biome] || BIOME.C;
}
function baseRadius(n) {
  if (n.type === "macro") return 9;
  if (n.type === "event") return 5.5;
  return 4 + (n.energy || 0.5) * 3.5;
}

/* ── Demo graph generator — a plausible HMG when no data is supplied ───────── */
function makeDemoGraph(seed = 1) {
  let s = seed;
  const rnd = () => (s = (s * 9301 + 49297) % 233280) / 233280;
  const biomes = ["A", "B", "C"];
  const topics = ["trip to Lisbon", "prefers dark mode", "sister's birthday", "django migration bug", "morning runs", "coffee: oat milk", "Q3 roadmap", "hates meetings before 10", "learning cello", "mom's phone number", "deploy on Fridays = bad", "loves sci-fi", "apartment lease ends May", "allergic to walnuts", "standup at 9:30", "side project: HMG", "favorite: ramen", "car needs service", "reading Dune", "dentist next Tue"];
  const nodes = [];
  const macros = ["Work", "Personal", "Health"];
  macros.forEach((m, i) => nodes.push({
    id: "M" + i,
    type: "macro",
    biome: biomes[i],
    label: m,
    energy: 1,
    valence: i === 2 ? 0.6 : 0.1
  }));
  for (let i = 0; i < 34; i++) {
    const t = rnd() < 0.12 ? "event" : "micro";
    nodes.push({
      id: "n" + i,
      type: t,
      biome: biomes[Math.floor(rnd() * 3)],
      label: topics[i % topics.length],
      energy: 0.3 + rnd() * 0.7,
      valence: rnd() * 2 - 1
    });
  }
  const edges = [];
  // attach each micro/event to a macro (Turn_Response structure)
  nodes.filter(n => n.type !== "macro").forEach(n => {
    const m = nodes[Math.floor(rnd() * 3)];
    edges.push({
      src: m.id,
      dst: n.id,
      type: "Turn_Response"
    });
  });
  // cross-links between micros (more Turn_Response)
  for (let i = 0; i < 24; i++) {
    const a = nodes[3 + Math.floor(rnd() * (nodes.length - 3))];
    const b = nodes[3 + Math.floor(rnd() * (nodes.length - 3))];
    if (a.id !== b.id) edges.push({
      src: a.id,
      dst: b.id,
      type: "Turn_Response"
    });
  }
  // wormholes — sparse purple emotional bridges across biomes
  for (let i = 0; i < 9; i++) {
    const a = nodes[3 + Math.floor(rnd() * (nodes.length - 3))];
    const b = nodes[3 + Math.floor(rnd() * (nodes.length - 3))];
    if (a.id !== b.id && a.biome !== b.biome) edges.push({
      src: a.id,
      dst: b.id,
      type: "Wormhole"
    });
  }
  return {
    nodes,
    edges
  };
}

/**
 * HmgGraph — an Obsidian-style force-directed view of the Hyper-Modified Grid
 * memory. Glowing nodes (micro / macro / event) coloured by biome, gray
 * Turn_Response structure links and purple Wormhole bridges. Fully interactive:
 * hover to focus a node + its neighbours, drag nodes, drag the background to
 * pan, scroll to zoom. Runs a continuous gentle physics simulation.
 */
function HmgGraph({
  nodes: nodesProp,
  edges: edgesProp,
  showEdges = true,
  showWormholes = true,
  showLabels = "hover",
  // "hover" | "macro" | "all" | "none"
  height = 420,
  background = "hsl(228 12% 7%)",
  style,
  ...rest
}) {
  const wrapRef = React.useRef(null);
  const canvasRef = React.useRef(null);
  const stateRef = React.useRef(null);

  // Build/refresh the simulation state when data changes
  const data = React.useMemo(() => {
    if (nodesProp && nodesProp.length) return {
      nodes: nodesProp,
      edges: edgesProp || []
    };
    return makeDemoGraph(7);
  }, [nodesProp, edgesProp]);
  React.useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");

    // ── init physics ──────────────────────────────────────────────────────
    const N = data.nodes.map((n, i) => ({
      ...n,
      x: Math.cos(i / data.nodes.length * Math.PI * 2) * (60 + i % 7 * 18),
      y: Math.sin(i / data.nodes.length * Math.PI * 2) * (60 + i % 5 * 18),
      vx: 0,
      vy: 0,
      r: baseRadius(n)
    }));
    const idx = new Map(N.map((n, i) => [n.id, i]));
    const E = data.edges.filter(e => idx.has(e.src) && idx.has(e.dst)).map(e => ({
      a: idx.get(e.src),
      b: idx.get(e.dst),
      type: e.type
    }));
    // adjacency for hover focus
    const adj = N.map(() => new Set());
    E.forEach(e => {
      adj[e.a].add(e.b);
      adj[e.b].add(e.a);
    });
    const view = {
      scale: 1,
      tx: 0,
      ty: 0
    };
    const S = {
      N,
      E,
      adj,
      view,
      hover: -1,
      drag: -1,
      panning: false,
      last: {
        x: 0,
        y: 0
      },
      W: 0,
      H: 0,
      alpha: 1,
      raf: 0
    };
    stateRef.current = S;
    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = wrap.clientWidth;
      const h = height;
      S.W = w;
      S.H = h;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);

    // ── force step ────────────────────────────────────────────────────────
    function step() {
      const a = S.alpha;
      // repulsion (O(n^2) — fine for a few hundred nodes)
      for (let i = 0; i < N.length; i++) {
        const ni = N[i];
        for (let j = i + 1; j < N.length; j++) {
          const nj = N[j];
          let dx = ni.x - nj.x,
            dy = ni.y - nj.y;
          let d2 = dx * dx + dy * dy || 0.01;
          const rep = 900 / d2;
          const d = Math.sqrt(d2);
          const fx = dx / d * rep,
            fy = dy / d * rep;
          ni.vx += fx * a;
          ni.vy += fy * a;
          nj.vx -= fx * a;
          nj.vy -= fy * a;
        }
      }
      // link springs
      for (const e of E) {
        const A = N[e.a],
          B = N[e.b];
        let dx = B.x - A.x,
          dy = B.y - A.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
        const rest = e.type === "Wormhole" ? 150 : 74;
        const k = e.type === "Wormhole" ? 0.006 : 0.02;
        const f = (d - rest) * k;
        const fx = dx / d * f,
          fy = dy / d * f;
        A.vx += fx * a;
        A.vy += fy * a;
        B.vx -= fx * a;
        B.vy -= fy * a;
      }
      // gravity to center + integrate
      for (let i = 0; i < N.length; i++) {
        const n = N[i];
        n.vx -= n.x * 0.0016 * a;
        n.vy -= n.y * 0.0016 * a;
        if (i === S.drag) {
          n.vx = 0;
          n.vy = 0;
          continue;
        }
        n.vx *= 0.86;
        n.vy *= 0.86;
        n.x += n.vx;
        n.y += n.vy;
      }
      if (S.alpha > 0.06) S.alpha *= 0.996; // cool down but never fully freeze (gentle drift)
    }

    // ── render ────────────────────────────────────────────────────────────
    function toScreen(n) {
      return {
        x: S.W / 2 + view.tx + n.x * view.scale,
        y: S.H / 2 + view.ty + n.y * view.scale
      };
    }
    function draw() {
      ctx.clearRect(0, 0, S.W, S.H);
      const focus = S.hover >= 0 ? S.hover : S.drag;
      const focused = focus >= 0;

      // edges
      if (showEdges) {
        for (const e of E) {
          if (e.type === "Wormhole" && !showWormholes) continue;
          const A = toScreen(N[e.a]),
            B = toScreen(N[e.b]);
          const near = focused && (e.a === focus || e.b === focus);
          if (e.type === "Wormhole") {
            ctx.strokeStyle = near ? "rgba(167,139,250,0.95)" : focused ? "rgba(167,139,250,0.18)" : EDGE.Wormhole;
            ctx.lineWidth = near ? 1.8 : 1.2;
          } else {
            ctx.strokeStyle = near ? "rgba(45,212,191,0.5)" : EDGE.Turn_Response;
            ctx.lineWidth = near ? 1.2 : 0.7;
          }
          ctx.beginPath();
          ctx.moveTo(A.x, A.y);
          ctx.lineTo(B.x, B.y);
          ctx.stroke();
        }
      }

      // nodes
      for (let i = 0; i < N.length; i++) {
        const n = N[i];
        const p = toScreen(n);
        const col = nodeColor(n);
        const dim = focused && i !== focus && !S.adj[focus].has(i);
        const r = n.r * view.scale * (n.type === "macro" ? 1 : 1) * (i === focus ? 1.35 : 1);
        ctx.globalAlpha = dim ? 0.18 : 1;
        // glow halo
        ctx.shadowColor = col;
        ctx.shadowBlur = (n.type === "macro" ? 22 : 12) * (i === focus ? 1.6 : 1);
        ctx.fillStyle = col;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
        // core ring for macro
        if (n.type === "macro") {
          ctx.globalAlpha = dim ? 0.2 : 0.9;
          ctx.fillStyle = "rgba(255,255,255,0.85)";
          ctx.beginPath();
          ctx.arc(p.x, p.y, r * 0.34, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.globalAlpha = 1;

        // labels
        const wantLabel = showLabels === "all" || showLabels === "macro" && n.type === "macro" || showLabels === "hover" && (i === focus || focused && S.adj[focus].has(i)) || showLabels === "macro" && false;
        if (wantLabel && n.label && !dim) {
          ctx.font = `${n.type === "macro" ? 600 : 400} ${n.type === "macro" ? 12 : 11}px Inter, sans-serif`;
          ctx.fillStyle = i === focus ? "rgba(240,244,250,0.98)" : "rgba(205,214,222,0.8)";
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          ctx.fillText(n.label, p.x, p.y + r + 4);
        }
      }
    }
    function frame() {
      step();
      draw();
      S.raf = requestAnimationFrame(frame);
    }
    frame();

    // ── interaction ───────────────────────────────────────────────────────
    function pick(mx, my) {
      for (let i = N.length - 1; i >= 0; i--) {
        const p = toScreen(N[i]);
        const rr = N[i].r * view.scale + 6;
        if ((mx - p.x) ** 2 + (my - p.y) ** 2 <= rr * rr) return i;
      }
      return -1;
    }
    function pos(ev) {
      const rect = canvas.getBoundingClientRect();
      const t = ev.touches ? ev.touches[0] : ev;
      return {
        x: t.clientX - rect.left,
        y: t.clientY - rect.top
      };
    }
    function onMove(ev) {
      const {
        x,
        y
      } = pos(ev);
      if (S.drag >= 0) {
        const n = N[S.drag];
        n.x = (x - S.W / 2 - view.tx) / view.scale;
        n.y = (y - S.H / 2 - view.ty) / view.scale;
        S.alpha = Math.max(S.alpha, 0.5);
        return;
      }
      if (S.panning) {
        view.tx += x - S.last.x;
        view.ty += y - S.last.y;
        S.last = {
          x,
          y
        };
        return;
      }
      const h = pick(x, y);
      S.hover = h;
      canvas.style.cursor = h >= 0 ? "grab" : "default";
    }
    function onDown(ev) {
      const {
        x,
        y
      } = pos(ev);
      const h = pick(x, y);
      if (h >= 0) {
        S.drag = h;
        canvas.style.cursor = "grabbing";
      } else {
        S.panning = true;
        S.last = {
          x,
          y
        };
        canvas.style.cursor = "move";
      }
    }
    function onUp() {
      S.drag = -1;
      S.panning = false;
      canvas.style.cursor = "default";
    }
    function onWheel(ev) {
      ev.preventDefault();
      const {
        x,
        y
      } = pos(ev);
      const cx = x - S.W / 2 - view.tx,
        cy = y - S.H / 2 - view.ty;
      const f = ev.deltaY < 0 ? 1.1 : 1 / 1.1;
      const ns = Math.min(3, Math.max(0.35, view.scale * f));
      view.tx -= cx * (ns / view.scale - 1);
      view.ty -= cy * (ns / view.scale - 1);
      view.scale = ns;
    }
    canvas.addEventListener("mousemove", onMove);
    canvas.addEventListener("mousedown", onDown);
    window.addEventListener("mouseup", onUp);
    canvas.addEventListener("wheel", onWheel, {
      passive: false
    });
    canvas.addEventListener("touchstart", onDown, {
      passive: true
    });
    canvas.addEventListener("touchmove", onMove, {
      passive: true
    });
    canvas.addEventListener("touchend", onUp);
    return () => {
      cancelAnimationFrame(S.raf);
      ro.disconnect();
      canvas.removeEventListener("mousemove", onMove);
      canvas.removeEventListener("mousedown", onDown);
      window.removeEventListener("mouseup", onUp);
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("touchstart", onDown);
      canvas.removeEventListener("touchmove", onMove);
      canvas.removeEventListener("touchend", onUp);
    };
  }, [data, showEdges, showWormholes, showLabels, height]);
  return /*#__PURE__*/React.createElement("div", _extends({
    ref: wrapRef,
    style: {
      position: "relative",
      width: "100%",
      height,
      borderRadius: "var(--radius-lg)",
      overflow: "hidden",
      background,
      backgroundImage: "radial-gradient(120% 80% at 50% 40%, hsl(228 14% 12% / 0.9), hsl(228 12% 6%))",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("canvas", {
    ref: canvasRef,
    style: {
      display: "block"
    }
  }));
}
Object.assign(__ds_scope, { HmgGraph });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/HmgGraph/HmgGraph.jsx", error: String((e && e.message) || e) }); }

// components/HmgHexGrid/HmgHexGrid.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* ── HMG hex palette ──────────────────────────────────────────────────────── */
const GRAY = "#8892B0";
const GOLD = "#E0A83A";
const GREEN = "#43C463";
const MACRO_LINK = "rgba(224,168,58,0.30)";

/* axial helpers */
function hexDist(a, b) {
  return (Math.abs(a.q - b.q) + Math.abs(a.q + a.r - b.q - b.r) + Math.abs(a.r - b.r)) / 2;
}
function hexSpiral(n) {
  const out = [{
    q: 0,
    r: 0
  }];
  const DIRS = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]];
  let k = 1;
  while (out.length < n) {
    let q = DIRS[4][0] * k,
      r = DIRS[4][1] * k;
    for (let side = 0; side < 6 && out.length < n; side++) {
      for (let step = 0; step < k && out.length < n; step++) {
        out.push({
          q,
          r
        });
        q += DIRS[side][0];
        r += DIRS[side][1];
      }
    }
    k++;
  }
  return out;
}
const LABELS = ["Golden Retriever", "Dog Loves Swimming", "Route Project Sw", "Building a Boat", "Coupling Measure", "Sister Summer", "Night Owl", "Dream Loop Memor", "Choosing a Map S", "Hello", "Greetings", "Choosing OSM for", "Need Assistance", "Memory Retrieval", "Memory Companion", "Notes and Memori", "What Else?", "Personal Details", "Morning Runs", "Oat Milk Coffee", "Lease Ends May", "Cello Practice", "Q3 Roadmap", "Standup 9:30", "Reading Dune", "Deploy Fridays", "Walnut Allergy", "Dentist Tuesday"];
function makeDemo(count = 24) {
  const coords = hexSpiral(count);
  const seedIdx = [3, 8, 15];
  const seeds = seedIdx.map(i => coords[i]);
  const macroLabels = ["personal", "dog", "project"];
  const nodes = coords.map((c, i) => {
    let best = 0,
      bd = 1e9;
    seeds.forEach((s, si) => {
      const d = hexDist(c, s);
      if (d < bd) {
        bd = d;
        best = si;
      }
    });
    const seedOf = seedIdx.indexOf(i);
    const isSeed = seedOf >= 0;
    return {
      id: "h" + i,
      q: c.q,
      r: c.r,
      ord: i,
      cluster: best,
      type: isSeed ? "macro" : "micro",
      label: isSeed ? "Macro: " + macroLabels[seedOf] : LABELS[i % LABELS.length],
      energy: isSeed ? 1 : 0.35 + i * 37 % 60 / 100
    };
  });
  const act = nodes.find(n => n.type === "micro");
  if (act) act.active = true;
  nodes.filter(n => n.type === "macro").forEach(m => {
    m.count = nodes.filter(n => n.cluster === m.cluster && n.type === "micro").length;
  });
  // macro ↔ macro connections (some macros are linked to others)
  const macroLinks = [[0, 1], [1, 2]];
  return {
    nodes,
    macroLinks
  };
}

/**
 * HmgHexGrid — the HMG honeycomb hex view with live macro-compression (Λ).
 * Micro memories are gray hexes; a cluster of related micros compresses into a
 * gold-outlined MACRO hex (◆ Macro: …). Compressing a cluster pulls the
 * remaining hexes together so the grid stays gap-free (they attract into a
 * compact honeycomb). Macros can also be linked to other macros. Hover a macro
 * to light its cluster; click it — or "Compress all" — to animate the collapse;
 * drag to pan, scroll to zoom.
 */
function HmgHexGrid({
  nodes: nodesProp,
  macroLinks: macroLinksProp,
  size = 34,
  showEdges = true,
  showLabels = true,
  height = 460,
  background = "hsl(228 12% 6%)",
  onCompressChange,
  style,
  ...rest
}) {
  const wrapRef = React.useRef(null);
  const canvasRef = React.useRef(null);
  const apiRef = React.useRef(null);
  const [allCompressed, setAllCompressed] = React.useState(false);
  const data = React.useMemo(() => {
    if (nodesProp && nodesProp.length) {
      // stable spiral order for provided data
      const withOrd = nodesProp.map((n, i) => ({
        ...n,
        ord: n.ord != null ? n.ord : i
      }));
      const ordered = [...withOrd].sort((a, b) => {
        const da = hexDist({
            q: a.q,
            r: a.r
          }, {
            q: 0,
            r: 0
          }),
          db = hexDist({
            q: b.q,
            r: b.r
          }, {
            q: 0,
            r: 0
          });
        if (da !== db) return da - db;
        return Math.atan2(a.r, a.q) - Math.atan2(b.r, b.q);
      });
      ordered.forEach((n, i) => {
        n.ord = i;
      });
      return {
        nodes: withOrd,
        macroLinks: macroLinksProp || []
      };
    }
    return makeDemo(24);
  }, [nodesProp, macroLinksProp]);
  React.useEffect(() => {
    const canvas = canvasRef.current,
      wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");
    const N = data.nodes.map(n => ({
      ...n,
      px: 0,
      py: 0,
      sc: 1
    }));
    const macros = N.filter(n => n.type === "macro");
    const macroByCluster = {};
    macros.forEach(m => {
      macroByCluster[m.cluster] = m;
    });
    // resolve macro-macro links to node refs
    const mlinks = (data.macroLinks || []).map(pair => [macroByCluster[pair[0]], macroByCluster[pair[1]]]).filter(p => p[0] && p[1]);

    // packing spiral (world axial cells), plenty of room
    const SPIRAL = hexSpiral(N.length + 6);
    function axialToWorld(cell) {
      return {
        x: size * Math.sqrt(3) * (cell.q + cell.r / 2),
        y: size * 1.5 * cell.r
      };
    }
    // init positions at original cells
    N.forEach(n => {
      const p = axialToWorld({
        q: n.q,
        r: n.r
      });
      n.px = p.x;
      n.py = p.y;
    });

    // compression intent per cluster (0/1) + animated value
    const target = {};
    const comp = {};
    macros.forEach(m => {
      target[m.cluster] = 0;
      comp[m.cluster] = 0;
    });
    const view = {
      scale: 1,
      tx: 0,
      ty: 0
    };
    const S = {
      hover: -1,
      panning: false,
      last: {
        x: 0,
        y: 0
      },
      W: 0,
      H: 0,
      raf: 0,
      pulse: 0
    };
    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      S.W = wrap.clientWidth;
      S.H = height;
      canvas.width = S.W * dpr;
      canvas.height = S.H * dpr;
      canvas.style.width = S.W + "px";
      canvas.style.height = S.H + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);
    function toScreen(px, py) {
      return {
        x: S.W / 2 + view.tx + px * view.scale,
        y: S.H / 2 + view.ty + py * view.scale
      };
    }

    // ── layout: compute packed target cell for every node each frame ──────────
    const orderIdx = [...N].sort((a, b) => a.ord - b.ord);
    function computeTargets() {
      // visible = macros + micros whose cluster is NOT compressed
      const visible = orderIdx.filter(n => n.type === "macro" || target[n.cluster] < 0.5);
      const cellOf = new Map();
      visible.forEach((n, i) => cellOf.set(n.id, SPIRAL[i]));
      for (const n of N) {
        let cell, tsc;
        if (n.type === "micro" && target[n.cluster] >= 0.5) {
          const m = macroByCluster[n.cluster];
          cell = cellOf.get(m.id) || {
            q: m.q,
            r: m.r
          };
          tsc = 0;
        } else {
          cell = cellOf.get(n.id) || {
            q: n.q,
            r: n.r
          };
          tsc = 1;
        }
        const w = axialToWorld(cell);
        n._tx = w.x;
        n._ty = w.y;
        n._tsc = tsc;
      }
    }
    function hexPath(cx, cy, r) {
      ctx.beginPath();
      for (let i = 0; i < 6; i++) {
        const a = Math.PI / 180 * (60 * i - 90);
        const x = cx + r * Math.cos(a),
          y = cy + r * Math.sin(a);
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      }
      ctx.closePath();
    }
    function drawLabel(text, cx, cy, r, color, weight, fs) {
      ctx.font = `${weight} ${fs}px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const maxW = r * 1.7;
      let t = text;
      if (ctx.measureText(t).width > maxW) {
        while (t.length > 2 && ctx.measureText(t + "…").width > maxW) t = t.slice(0, -1);
        t += "…";
      }
      ctx.fillStyle = color;
      ctx.fillText(t, cx, cy);
    }
    function draw() {
      ctx.clearRect(0, 0, S.W, S.H);
      const hoverNode = S.hover >= 0 ? N[S.hover] : null;
      const hoverCluster = hoverNode ? hoverNode.cluster : -999;

      // edges: micro → macro (within cluster)
      if (showEdges) {
        for (const n of N) {
          if (n.type !== "micro") continue;
          const m = macroByCluster[n.cluster];
          if (!m) continue;
          if (n.sc < 0.15) continue; // absorbed → skip
          const a = toScreen(n.px, n.py),
            b = toScreen(m.px, m.py);
          const lit = hoverCluster === n.cluster;
          ctx.strokeStyle = lit ? "rgba(224,168,58,0.5)" : "rgba(150,160,190,0.10)";
          ctx.lineWidth = lit ? 1.3 : 0.7;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
        // macro ↔ macro connections
        for (const [m1, m2] of mlinks) {
          const a = toScreen(m1.px, m1.py),
            b = toScreen(m2.px, m2.py);
          const lit = hoverCluster === m1.cluster || hoverCluster === m2.cluster;
          ctx.strokeStyle = lit ? "rgba(224,168,58,0.7)" : MACRO_LINK;
          ctx.lineWidth = lit ? 2 : 1.2;
          ctx.setLineDash([4, 3]);
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      }

      // draw micros then macros
      const drawOrder = [...N].sort((a, b) => (a.type === "macro") - (b.type === "macro"));
      for (const n of drawOrder) {
        const p = toScreen(n.px, n.py);
        const inHoverCluster = hoverCluster === n.cluster;
        const idxHover = hoverNode === n;
        if (n.type === "micro") {
          if (n.sc <= 0.04) continue;
          const r = size * view.scale * 0.9 * n.sc;
          const op = (0.25 + n.energy * 0.5) * (hoverNode && !inHoverCluster ? 0.4 : 1) * n.sc;
          hexPath(p.x, p.y, r);
          ctx.fillStyle = n.active ? GREEN : GRAY;
          ctx.globalAlpha = n.active ? 0.9 * n.sc : op;
          if (n.active) {
            ctx.shadowColor = GREEN;
            ctx.shadowBlur = 18 * (0.6 + 0.4 * Math.sin(S.pulse));
          }
          ctx.fill();
          ctx.shadowBlur = 0;
          ctx.globalAlpha = 1;
          hexPath(p.x, p.y, r);
          if (inHoverCluster || idxHover) {
            ctx.strokeStyle = GOLD;
            ctx.lineWidth = 1.5;
          } else {
            ctx.strokeStyle = "rgba(20,22,30,0.9)";
            ctx.lineWidth = 1;
          }
          ctx.stroke();
          if (showLabels && n.sc > 0.6) drawLabel(n.label, p.x, p.y, r, "rgba(210,216,230," + 0.72 * n.sc + ")", 400, 11);
        } else {
          const grow = 1 + 0.28 * (comp[n.cluster] || 0);
          const r = size * view.scale * grow;
          hexPath(p.x, p.y, r);
          ctx.fillStyle = "rgba(224,168,58,0.14)";
          ctx.globalAlpha = hoverNode && !inHoverCluster ? 0.5 : 1;
          ctx.fill();
          hexPath(p.x, p.y, r);
          ctx.strokeStyle = GOLD;
          ctx.lineWidth = idxHover ? 3 : 2.2;
          if (idxHover || inHoverCluster) {
            ctx.shadowColor = GOLD;
            ctx.shadowBlur = 14;
          }
          ctx.stroke();
          ctx.shadowBlur = 0;
          ctx.globalAlpha = 1;
          if (showLabels) {
            const n2 = (comp[n.cluster] || 0) > 0.5 ? ` (${n.count})` : "";
            drawLabel("◆ " + n.label + n2, p.x, p.y, r, "rgba(240,224,180,0.95)", 600, 11);
          }
        }
      }
    }
    function frame() {
      S.pulse += 0.06;
      // animate compression value
      for (const k in target) {
        const d = target[k] - comp[k];
        comp[k] = Math.abs(d) > 0.001 ? comp[k] + d * 0.14 : target[k];
      }
      computeTargets();
      // ease positions + scale toward targets (this is the "attract to fill gaps")
      for (const n of N) {
        n.px += (n._tx - n.px) * 0.16;
        n.py += (n._ty - n.py) * 0.16;
        n.sc += (n._tsc - n.sc) * 0.16;
      }
      draw();
      S.raf = requestAnimationFrame(frame);
    }
    frame();

    // ── interaction ───────────────────────────────────────────────────────
    function pos(ev) {
      const rect = canvas.getBoundingClientRect();
      const t = ev.touches ? ev.touches[0] : ev;
      return {
        x: t.clientX - rect.left,
        y: t.clientY - rect.top
      };
    }
    function pick(mx, my) {
      const order = [...N].map((n, i) => ({
        n,
        i
      })).sort((a, b) => (a.n.type === "macro") - (b.n.type === "macro"));
      for (let k = order.length - 1; k >= 0; k--) {
        const {
          n,
          i
        } = order[k];
        if (n.type === "micro" && n.sc < 0.4) continue;
        const p = toScreen(n.px, n.py);
        const r = size * view.scale * (n.type === "macro" ? 1.05 : 0.9);
        if (Math.abs(mx - p.x) < r * 0.86 && Math.abs(my - p.y) < r) return i;
      }
      return -1;
    }
    function onMove(ev) {
      const {
        x,
        y
      } = pos(ev);
      if (S.panning) {
        view.tx += x - S.last.x;
        view.ty += y - S.last.y;
        S.last = {
          x,
          y
        };
        return;
      }
      const h = pick(x, y);
      S.hover = h;
      canvas.style.cursor = h >= 0 ? N[h].type === "macro" ? "pointer" : "grab" : "default";
    }
    function onDown(ev) {
      const {
        x,
        y
      } = pos(ev);
      const h = pick(x, y);
      if (h >= 0 && N[h].type === "macro") {
        const c = N[h].cluster;
        target[c] = target[c] > 0.5 ? 0 : 1;
        syncAll();
      } else {
        S.panning = true;
        S.last = {
          x,
          y
        };
        canvas.style.cursor = "move";
      }
    }
    function onUp() {
      S.panning = false;
      canvas.style.cursor = "default";
    }
    function onWheel(ev) {
      ev.preventDefault();
      const {
        x,
        y
      } = pos(ev);
      const cx = x - S.W / 2 - view.tx,
        cy = y - S.H / 2 - view.ty;
      const f = ev.deltaY < 0 ? 1.1 : 1 / 1.1;
      const ns = Math.min(2.4, Math.max(0.4, view.scale * f));
      view.tx -= cx * (ns / view.scale - 1);
      view.ty -= cy * (ns / view.scale - 1);
      view.scale = ns;
    }
    function syncAll() {
      const anyOpen = Object.values(target).some(v => v < 0.5);
      setAllCompressed(!anyOpen);
      onCompressChange && onCompressChange(!anyOpen);
    }
    canvas.addEventListener("mousemove", onMove);
    canvas.addEventListener("mousedown", onDown);
    window.addEventListener("mouseup", onUp);
    canvas.addEventListener("wheel", onWheel, {
      passive: false
    });
    apiRef.current = {
      setAll(v) {
        for (const k in target) target[k] = v ? 1 : 0;
      }
    };
    return () => {
      cancelAnimationFrame(S.raf);
      ro.disconnect();
      canvas.removeEventListener("mousemove", onMove);
      canvas.removeEventListener("mousedown", onDown);
      window.removeEventListener("mouseup", onUp);
      canvas.removeEventListener("wheel", onWheel);
    };
  }, [data, size, showEdges, showLabels, height]);
  const toggleAll = () => {
    const v = !allCompressed;
    setAllCompressed(v);
    apiRef.current && apiRef.current.setAll(v);
    onCompressChange && onCompressChange(v);
  };
  return /*#__PURE__*/React.createElement("div", _extends({
    ref: wrapRef,
    style: {
      position: "relative",
      width: "100%",
      height,
      borderRadius: "var(--radius-lg)",
      overflow: "hidden",
      background,
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("canvas", {
    ref: canvasRef,
    style: {
      display: "block"
    }
  }), /*#__PURE__*/React.createElement("button", {
    onClick: toggleAll,
    style: {
      position: "absolute",
      top: 10,
      right: 10,
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      padding: "5px 10px",
      borderRadius: "var(--radius-md)",
      border: "1px solid " + GOLD,
      background: allCompressed ? GOLD : "hsl(228 12% 11% / 0.85)",
      color: allCompressed ? "#1a1608" : GOLD,
      fontFamily: "var(--font-sans)",
      fontSize: 11,
      fontWeight: 600,
      cursor: "pointer",
      backdropFilter: "blur(6px)"
    }
  }, allCompressed ? "Expand all" : "Compress all"));
}
Object.assign(__ds_scope, { HmgHexGrid });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/HmgHexGrid/HmgHexGrid.jsx", error: String((e && e.message) || e) }); }

// components/IconButton/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * IconButton — the square, icon-only control the app uses everywhere in
 * headers, toolbars and rows (h-8 w-8 rounded-lg, muted → foreground on hover).
 */
function IconButton({
  size = "md",
  variant = "ghost",
  active = false,
  disabled = false,
  title,
  children,
  style,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const dims = {
    sm: 28,
    md: 32,
    lg: 36
  };
  const d = dims[size] || 32;
  const base = {
    color: active ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))",
    background: active ? "hsl(var(--primary) / 0.1)" : "transparent"
  };
  const hoverStyle = variant === "danger" ? {
    color: "hsl(var(--destructive))",
    background: "hsl(var(--destructive) / 0.1)"
  } : {
    color: "hsl(var(--foreground))",
    background: "hsl(var(--surface-hover))"
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    title: title,
    disabled: disabled,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      height: d,
      width: d,
      flexShrink: 0,
      borderRadius: "var(--radius-md)",
      border: "none",
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1,
      transition: "background var(--dur-fast), color var(--dur-fast)",
      ...base,
      ...(hover && !disabled && !active ? hoverStyle : null),
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/IconButton/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/Input/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Input — text field with the app's dark inset styling and optional leading
 * icon. Border goes teal + faint teal ring on focus.
 */
function Input({
  leftIcon,
  type = "text",
  disabled = false,
  surface = "field",
  style,
  wrapperStyle,
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  // "field" = bg-surface-2 (login/search); "flush" = bg-background (rows)
  const bg = surface === "flush" ? "hsl(var(--background))" : "hsl(var(--surface-2))";
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      display: "flex",
      alignItems: "center",
      ...wrapperStyle
    }
  }, leftIcon && /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      left: 12,
      display: "inline-flex",
      color: "hsl(var(--muted-foreground))",
      pointerEvents: "none"
    }
  }, leftIcon), /*#__PURE__*/React.createElement("input", _extends({
    type: type,
    disabled: disabled,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      width: "100%",
      height: 44,
      padding: leftIcon ? "0 16px 0 40px" : "0 16px",
      fontFamily: "var(--font-sans)",
      fontSize: 14,
      color: "hsl(var(--foreground))",
      background: bg,
      border: `1px solid ${focus ? "hsl(var(--primary))" : "hsl(var(--border))"}`,
      borderRadius: "var(--radius-md)",
      outline: "none",
      boxShadow: focus ? "0 0 0 3px hsl(var(--primary) / 0.3)" : "none",
      transition: "border-color var(--dur-fast), box-shadow var(--dur-fast)",
      opacity: disabled ? 0.5 : 1,
      ...style
    }
  }, rest)));
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/Input/Input.jsx", error: String((e && e.message) || e) }); }

// components/MessageBubble/MessageBubble.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * MessageBubble — a chat turn. User turns are right-aligned in a surface-3
 * bubble with a faint blue (user-border) edge; agent turns are left-aligned
 * with NO bubble — just foreground text on the canvas (the app's key move).
 */
function MessageBubble({
  role = "assistant",
  timestamp,
  children,
  style,
  ...rest
}) {
  const isUser = role === "user";
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      display: "flex",
      flexDirection: "column",
      alignItems: isUser ? "flex-end" : "flex-start",
      padding: "6px 16px",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "80%",
      fontSize: 14,
      lineHeight: 1.65,
      color: "hsl(var(--foreground))",
      borderRadius: isUser ? "var(--radius-xl)" : 0,
      padding: isUser ? "10px 16px" : 0,
      background: isUser ? "hsl(var(--surface-3))" : "transparent",
      border: isUser ? "1px solid hsl(var(--user-border) / 0.3)" : "none",
      whiteSpace: "pre-wrap",
      wordBreak: "break-word"
    }
  }, children), timestamp && /*#__PURE__*/React.createElement("span", {
    style: {
      marginTop: 2,
      fontSize: 10,
      color: "hsl(var(--muted-foreground) / 0.6)",
      userSelect: "none"
    }
  }, timestamp));
}
Object.assign(__ds_scope, { MessageBubble });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/MessageBubble/MessageBubble.jsx", error: String((e && e.message) || e) }); }

// components/Pill/Pill.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const DOT_COLOR = {
  primary: "hsl(var(--primary))",
  active: "var(--status-active)",
  working: "var(--status-working)",
  done: "var(--status-done)",
  error: "var(--status-error)",
  thinking: "var(--thinking)"
};

/**
 * Pill — the app's signature rounded-full chip. Used for tool calls, thinking,
 * status, info and inline meta. Tiny (11px), surface-2 fill, optional leading
 * icon or a pulsing status dot.
 */
function Pill({
  icon,
  dot,
  pulse = false,
  tone = "muted",
  mono = false,
  children,
  style,
  ...rest
}) {
  const dotColor = DOT_COLOR[dot] || DOT_COLOR.primary;
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      borderRadius: "var(--radius-full)",
      background: "hsl(var(--surface-2))",
      padding: "2px 10px",
      fontFamily: mono ? "var(--font-mono)" : "var(--font-sans)",
      fontSize: 11,
      lineHeight: 1.4,
      color: tone === "primary" ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))",
      fontStyle: tone === "info" ? "italic" : "normal",
      maxWidth: "100%",
      ...style
    }
  }, rest), icon, dot && /*#__PURE__*/React.createElement("span", {
    style: {
      position: "relative",
      display: "inline-flex",
      height: 6,
      width: 6,
      flexShrink: 0
    }
  }, pulse && /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      inset: 0,
      borderRadius: "var(--radius-full)",
      background: dotColor,
      opacity: 0.75,
      animation: "pa-pulse-glow 2s ease-in-out infinite"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      position: "relative",
      height: 6,
      width: 6,
      borderRadius: "var(--radius-full)",
      background: dotColor
    }
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
    }
  }, children));
}
Object.assign(__ds_scope, { Pill });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/Pill/Pill.jsx", error: String((e && e.message) || e) }); }

// components/PlanTracker/PlanTracker.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const ICON = {
  done: {
    mark: "✓",
    color: "hsl(var(--status-done))"
  },
  active: {
    mark: "◐",
    color: "hsl(var(--primary))"
  },
  pending: {
    mark: "○",
    color: "hsl(var(--muted-foreground))"
  },
  error: {
    mark: "✕",
    color: "hsl(var(--status-error))"
  }
};

/**
 * PlanTracker — the agent's live plan / to-do. A titled card with a progress
 * bar and a checklist of steps (done / active / pending / error). Done steps
 * strike through; the active step is tinted with the accent.
 */
function PlanTracker({
  title = "Plan",
  steps = [],
  compact = false,
  style,
  ...rest
}) {
  const done = steps.filter(s => s.status === "done").length;
  const pct = steps.length ? done / steps.length * 100 : 0;
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      borderRadius: "var(--radius-lg)",
      border: "1px solid hsl(var(--border))",
      background: "hsl(var(--surface-2))",
      overflow: "hidden",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      padding: compact ? "8px 12px" : "10px 12px"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      fontWeight: 600,
      color: "hsl(var(--foreground))",
      flex: 1
    }
  }, title), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 11,
      color: "hsl(var(--muted-foreground))"
    }
  }, done, "/", steps.length)), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 2,
      background: "hsl(var(--border))"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: "100%",
      width: pct + "%",
      background: "hsl(var(--primary))",
      transition: "width var(--dur-slow) var(--ease-out)"
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "8px 12px",
      display: "flex",
      flexDirection: "column",
      gap: compact ? 4 : 6
    }
  }, steps.map((s, i) => {
    const ic = ICON[s.status] || ICON.pending;
    const isDone = s.status === "done";
    return /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        display: "flex",
        alignItems: "flex-start",
        gap: 8
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 12,
        lineHeight: "18px",
        color: ic.color,
        width: 12,
        textAlign: "center",
        flexShrink: 0,
        ...(s.status === "active" ? {
          animation: "pa-pulse-glow 1.6s ease-in-out infinite"
        } : null)
      }
    }, ic.mark), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 13,
        lineHeight: 1.4,
        color: isDone ? "hsl(var(--muted-foreground))" : s.status === "active" ? "hsl(var(--foreground))" : "hsl(var(--foreground))",
        textDecoration: isDone ? "line-through" : "none",
        opacity: s.status === "pending" ? 0.75 : 1
      }
    }, s.text));
  })));
}
Object.assign(__ds_scope, { PlanTracker });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/PlanTracker/PlanTracker.jsx", error: String((e && e.message) || e) }); }

// components/ProviderSelect/ProviderSelect.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * ProviderSelect — the model/provider picker from the left panel. A bordered
 * trigger (leading icon + label + chevron) that opens a menu of options; the
 * selected option is teal, and options can carry a small "free" tag.
 */
function ProviderSelect({
  options = [],
  value,
  onChange,
  icon,
  placeholder = "Select…",
  style,
  ...rest
}) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const h = e => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const current = options.find(o => o.id === value);
  return /*#__PURE__*/React.createElement("div", _extends({
    ref: ref,
    style: {
      position: "relative",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => setOpen(o => !o),
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      width: "100%",
      padding: "6px 10px",
      borderRadius: "var(--radius-md)",
      border: `1px solid ${open ? "hsl(var(--primary) / 0.4)" : "hsl(var(--border))"}`,
      background: "hsl(var(--background))",
      color: "hsl(var(--foreground))",
      fontFamily: "var(--font-sans)",
      fontSize: 12,
      cursor: "pointer",
      transition: "border-color var(--dur-fast)"
    }
  }, icon && /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      color: "hsl(var(--primary) / 0.7)"
    }
  }, icon), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      textAlign: "left"
    }
  }, current ? current.label : placeholder), /*#__PURE__*/React.createElement("span", {
    style: {
      color: "hsl(var(--muted-foreground))",
      fontSize: 10,
      transform: open ? "rotate(180deg)" : "none",
      transition: "transform var(--dur-fast)"
    }
  }, "\u25BE")), open && /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      left: 0,
      right: 0,
      top: "calc(100% + 4px)",
      zIndex: 50,
      borderRadius: "var(--radius-md)",
      border: "1px solid hsl(var(--border))",
      background: "hsl(var(--background))",
      boxShadow: "var(--shadow-lg)",
      overflow: "hidden"
    }
  }, options.map(o => {
    const selected = o.id === value;
    return /*#__PURE__*/React.createElement("button", {
      key: o.id,
      type: "button",
      onClick: () => {
        onChange && onChange(o.id, o);
        setOpen(false);
      },
      onMouseEnter: e => {
        if (!selected) e.currentTarget.style.background = "hsl(var(--sidebar-accent))";
      },
      onMouseLeave: e => {
        if (!selected) e.currentTarget.style.background = "transparent";
      },
      style: {
        display: "flex",
        alignItems: "center",
        gap: 8,
        width: "100%",
        padding: "8px 12px",
        border: "none",
        background: selected ? "hsl(var(--primary) / 0.05)" : "transparent",
        color: selected ? "hsl(var(--primary))" : "hsl(var(--foreground))",
        fontFamily: "var(--font-sans)",
        fontSize: 12,
        cursor: "pointer",
        textAlign: "left"
      }
    }, icon && /*#__PURE__*/React.createElement("span", {
      style: {
        display: "inline-flex",
        opacity: 0.6
      }
    }, icon), /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1
      }
    }, o.label), o.free && /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 9,
        fontWeight: 500,
        color: "hsl(158 64% 62%)"
      }
    }, "free"));
  })));
}
Object.assign(__ds_scope, { ProviderSelect });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/ProviderSelect/ProviderSelect.jsx", error: String((e && e.message) || e) }); }

// components/SessionRow/SessionRow.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const STATUS = {
  working: "var(--status-working)",
  active: "var(--status-active)",
  done: "var(--status-done)",
  error: "var(--status-error)"
};

/**
 * SessionRow — a single session item in the left panel. Title + status dot,
 * meta line ("12 msgs · 4h ago"), optional pin. Active row uses the
 * sidebar-accent fill; others brighten on hover.
 */
function SessionRow({
  title,
  meta,
  status,
  pinned = false,
  active = false,
  onClick,
  style,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const dot = STATUS[status];
  const pulse = status === "working" || status === "active";
  return /*#__PURE__*/React.createElement("div", _extends({
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: "flex",
      alignItems: "flex-start",
      gap: 4,
      width: "100%",
      padding: "10px 12px",
      borderRadius: "var(--radius-md)",
      cursor: "pointer",
      textAlign: "left",
      background: active ? "hsl(var(--sidebar-accent))" : hover ? "hsl(var(--sidebar-accent) / 0.5)" : "transparent",
      transition: "background var(--dur-fast)",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 6,
      fontSize: 14,
      fontWeight: 500,
      color: "hsl(var(--foreground))",
      lineHeight: 1.2
    }
  }, pinned && /*#__PURE__*/React.createElement("span", {
    style: {
      color: "hsl(var(--primary))",
      fontSize: 10
    }
  }, "\uD83D\uDCCC"), /*#__PURE__*/React.createElement("span", {
    style: {
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
    }
  }, title), dot && /*#__PURE__*/React.createElement("span", {
    style: {
      position: "relative",
      display: "inline-flex",
      height: 8,
      width: 8,
      flexShrink: 0
    }
  }, pulse && /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      inset: 0,
      borderRadius: "var(--radius-full)",
      background: dot,
      opacity: 0.75,
      animation: "pa-pulse-glow 1.6s ease-in-out infinite"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      position: "relative",
      height: 8,
      width: 8,
      borderRadius: "var(--radius-full)",
      background: dot
    }
  }))), meta && /*#__PURE__*/React.createElement("span", {
    style: {
      display: "block",
      marginTop: 2,
      fontSize: 11,
      color: "hsl(var(--muted-foreground))"
    }
  }, meta)), /*#__PURE__*/React.createElement("span", {
    style: {
      flexShrink: 0,
      marginTop: 2,
      color: "hsl(var(--muted-foreground))",
      fontSize: 14,
      opacity: hover ? 1 : 0,
      transition: "opacity var(--dur-fast)"
    }
  }, "\u22EF"));
}
Object.assign(__ds_scope, { SessionRow });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/SessionRow/SessionRow.jsx", error: String((e && e.message) || e) }); }

// components/ToolCallBlock/ToolCallBlock.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const STATUS = {
  running: {
    color: "hsl(var(--status-working))",
    label: "running",
    dot: true
  },
  success: {
    color: "hsl(var(--status-done))",
    label: "done"
  },
  error: {
    color: "hsl(var(--status-error))",
    label: "error"
  },
  pending: {
    color: "hsl(var(--muted-foreground))",
    label: "queued"
  }
};

/**
 * ToolCallBlock — an inline agent tool / command execution card. Mono header
 * with the tool name (or $ command), a status chip and duration; a collapsible
 * body shows arguments and streamed output with an exit code. The workhorse of
 * an agent transcript.
 */
function ToolCallBlock({
  name,
  command,
  status = "success",
  duration,
  output,
  args,
  exitCode,
  defaultOpen = false,
  icon,
  style,
  ...rest
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  const st = STATUS[status] || STATUS.success;
  const title = command ? command : name;
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      borderRadius: "var(--radius-md)",
      border: "1px solid hsl(var(--border))",
      background: "hsl(var(--surface-2))",
      overflow: "hidden",
      fontFamily: "var(--font-mono)",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("button", {
    onClick: () => setOpen(o => !o),
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      width: "100%",
      padding: "8px 10px",
      border: "none",
      background: "transparent",
      cursor: "pointer",
      textAlign: "left",
      color: "hsl(var(--foreground))"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "hsl(var(--muted-foreground))",
      fontSize: 10,
      width: 8
    }
  }, open ? "▾" : "▸"), icon && /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      color: "hsl(var(--primary))"
    }
  }, icon), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      flex: 1,
      minWidth: 0,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
    }
  }, command ? /*#__PURE__*/React.createElement("span", {
    style: {
      color: "hsl(var(--muted-foreground))"
    }
  }, "$ ") : null, title), typeof exitCode === "number" && status !== "running" && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10,
      color: exitCode === 0 ? "hsl(var(--status-done))" : "hsl(var(--status-error))"
    }
  }, "exit ", exitCode), /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 5
    }
  }, st.dot && /*#__PURE__*/React.createElement("span", {
    style: {
      height: 6,
      width: 6,
      borderRadius: 999,
      background: st.color,
      animation: "pa-pulse-glow 1.4s ease-in-out infinite"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10,
      color: st.color
    }
  }, st.label)), duration != null && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10,
      color: "hsl(var(--muted-foreground))"
    }
  }, duration)), open && /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: "1px solid hsl(var(--border))"
    }
  }, args && /*#__PURE__*/React.createElement("pre", {
    style: {
      margin: 0,
      padding: "8px 12px",
      fontSize: 11.5,
      color: "hsl(var(--muted-foreground))",
      whiteSpace: "pre-wrap",
      wordBreak: "break-word",
      borderBottom: output ? "1px solid hsl(var(--border))" : "none"
    }
  }, typeof args === "string" ? args : JSON.stringify(args, null, 2)), output != null && /*#__PURE__*/React.createElement("pre", {
    style: {
      margin: 0,
      padding: "8px 12px",
      fontSize: 11.5,
      lineHeight: 1.55,
      color: "hsl(var(--foreground))",
      whiteSpace: "pre-wrap",
      wordBreak: "break-word",
      maxHeight: 240,
      overflow: "auto"
    }
  }, output)));
}
Object.assign(__ds_scope, { ToolCallBlock });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/ToolCallBlock/ToolCallBlock.jsx", error: String((e && e.message) || e) }); }

// components/WidgetCard/WidgetCard.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * WidgetCard — the right-panel widget shell (port of WidgetWrapper).
 * Header: icon + title on the left, hover-revealed collapse / fullscreen /
 * close controls on the right. Body renders below, scrolls if tall.
 */
function WidgetCard({
  title,
  icon,
  defaultCollapsed = false,
  onClose,
  onFullscreen,
  toolbar,
  children,
  style,
  ...rest
}) {
  const [collapsed, setCollapsed] = React.useState(defaultCollapsed);
  const [hover, setHover] = React.useState(false);
  const Chevron = collapsed ? "▸" : "▾";
  const ctrlBtn = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    height: 22,
    width: 22,
    borderRadius: "var(--radius-sm)",
    border: "none",
    background: "transparent",
    color: "hsl(var(--muted-foreground))",
    cursor: "pointer",
    fontSize: 12,
    transition: "background var(--dur-fast), color var(--dur-fast)"
  };
  return /*#__PURE__*/React.createElement("div", _extends({
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      borderRadius: "var(--radius-lg)",
      border: "1px solid hsl(var(--border))",
      background: "hsl(var(--surface-2))",
      overflow: "hidden",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      padding: "8px 10px",
      borderBottom: collapsed ? "none" : "1px solid hsl(var(--border))"
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => setCollapsed(c => !c),
    style: {
      ...ctrlBtn,
      height: 20,
      width: 20,
      color: "hsl(var(--muted-foreground))"
    },
    title: collapsed ? "Expand" : "Collapse"
  }, Chevron), /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      color: "hsl(var(--primary))"
    }
  }, icon), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      fontSize: 12,
      fontWeight: 600,
      color: "hsl(var(--foreground))"
    }
  }, title), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 2,
      opacity: hover ? 1 : 0,
      transition: "opacity var(--dur-fast)"
    }
  }, onFullscreen && /*#__PURE__*/React.createElement("button", {
    style: ctrlBtn,
    onClick: onFullscreen,
    title: "Fullscreen"
  }, "\u2922"), onClose && /*#__PURE__*/React.createElement("button", {
    style: ctrlBtn,
    onClick: onClose,
    title: "Close"
  }, "\u2715"))), !collapsed && toolbar && /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexWrap: "wrap",
      alignItems: "center",
      gap: 6,
      padding: "8px 12px",
      borderBottom: "1px solid hsl(var(--border))"
    }
  }, toolbar), !collapsed && /*#__PURE__*/React.createElement("div", null, children));
}
Object.assign(__ds_scope, { WidgetCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/WidgetCard/WidgetCard.jsx", error: String((e && e.message) || e) }); }

// ui_kits/cowork/Canvas.jsx
try { (() => {
/* Cowork — right widget CANVAS (AG-UI). Free layout: drag, resize, expand, tidy.
   Default widgets sit beside ones the agent generates on the fly. */
function CoworkCanvas({
  widgets,
  onRemove,
  onAdd,
  open,
  onToggle
}) {
  const {
    CanvasWidget,
    HmgGraph,
    HmgHexGrid,
    PlanTracker,
    DiffView,
    IconButton
  } = window.PersonalAgentDesignSystem_94ad89;
  const {
    Icon
  } = window.PA;
  const bodyRef = React.useRef(null);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [layout, setLayout] = React.useState({});
  const [zmap, setZmap] = React.useState({});
  const [expandedId, setExpandedId] = React.useState(null);
  const zTop = React.useRef(1);
  const bodyW = () => bodyRef.current ? bodyRef.current.clientWidth : 388;

  // keep a layout entry for every widget; auto-place new ones by stacking
  React.useEffect(() => {
    setLayout(prev => {
      const next = {
        ...prev
      };
      const bw = bodyW() - 24;
      let maxY = 12;
      Object.keys(next).forEach(id => {
        if (widgets.find(w => w.id === id)) maxY = Math.max(maxY, next[id].y + next[id].h + 12);
      });
      widgets.forEach(w => {
        if (!next[w.id]) {
          next[w.id] = {
            x: 12,
            y: maxY,
            w: Math.max(200, bw),
            h: defaultH(w.type)
          };
          maxY += next[w.id].h + 12;
        }
      });
      Object.keys(next).forEach(id => {
        if (!widgets.find(w => w.id === id)) delete next[id];
      });
      return next;
    });
  }, [widgets]);
  const bringFront = id => setZmap(m => ({
    ...m,
    [id]: ++zTop.current
  }));
  const startDrag = id => e => {
    if (expandedId) return;
    e.preventDefault();
    bringFront(id);
    const l = layout[id];
    if (!l) return;
    const sx = e.clientX,
      sy = e.clientY,
      ox = l.x,
      oy = l.y,
      bw = bodyW();
    const move = ev => {
      let nx = Math.max(0, Math.min(ox + (ev.clientX - sx), bw - l.w));
      let ny = Math.max(0, oy + (ev.clientY - sy));
      setLayout(p => ({
        ...p,
        [id]: {
          ...p[id],
          x: nx,
          y: ny
        }
      }));
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  const startResize = id => e => {
    if (expandedId) return;
    e.preventDefault();
    e.stopPropagation();
    bringFront(id);
    const l = layout[id];
    if (!l) return;
    const sx = e.clientX,
      sy = e.clientY,
      ow = l.w,
      oh = l.h,
      bw = bodyW();
    const move = ev => {
      let nw = Math.max(190, Math.min(ow + (ev.clientX - sx), bw - l.x));
      let nh = Math.max(96, oh + (ev.clientY - sy));
      setLayout(p => ({
        ...p,
        [id]: {
          ...p[id],
          w: nw,
          h: nh
        }
      }));
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  const tidy = () => setLayout(() => {
    const bw = bodyW() - 24;
    let y = 12;
    const next = {};
    widgets.forEach(w => {
      next[w.id] = {
        x: 12,
        y,
        w: Math.max(200, bw),
        h: defaultH(w.type)
      };
      y += next[w.id].h + 12;
    });
    return next;
  });
  if (!open) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 6,
        width: 48,
        borderLeft: "1px solid hsl(var(--border))",
        background: "hsl(var(--surface-2))",
        padding: "12px 4px",
        flexShrink: 0
      }
    }, /*#__PURE__*/React.createElement(IconButton, {
      title: "Open canvas",
      onClick: onToggle
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "layout-grid",
      size: 16
    })));
  }
  const ADDABLE = [{
    type: "memory-graph",
    title: "Memory · Graph",
    icon: "network"
  }, {
    type: "memory-hex",
    title: "Memory · Hex",
    icon: "hexagon"
  }, {
    type: "plan",
    title: "Plan",
    icon: "list-todo"
  }, {
    type: "metric",
    title: "Metric",
    icon: "activity"
  }, {
    type: "diff",
    title: "Last edit",
    icon: "file-diff"
  }];
  const body = (w, innerH) => {
    const gh = Math.max(120, Math.round((innerH - 12) / 24) * 24); // quantized so graphs don't re-init every px
    switch (w.type) {
      case "memory-graph":
        return /*#__PURE__*/React.createElement("div", {
          style: {
            padding: 6,
            height: "100%"
          }
        }, /*#__PURE__*/React.createElement(HmgGraph, {
          height: gh,
          showLabels: "hover"
        }));
      case "memory-hex":
        return /*#__PURE__*/React.createElement("div", {
          style: {
            padding: 6,
            height: "100%"
          }
        }, /*#__PURE__*/React.createElement(HmgHexGrid, {
          height: gh,
          size: 24
        }));
      case "plan":
        return /*#__PURE__*/React.createElement(PlanTracker, {
          compact: true,
          title: w.title,
          steps: w.steps || DEFAULT_PLAN,
          style: {
            border: "none",
            background: "transparent"
          }
        });
      case "diff":
        return /*#__PURE__*/React.createElement("div", {
          style: {
            padding: 8
          }
        }, /*#__PURE__*/React.createElement(DiffView, {
          filename: w.filename || "src/memory/hmg.ts",
          diff: w.diff || DEFAULT_DIFF
        }));
      case "table":
        return /*#__PURE__*/React.createElement("div", null, (w.rows || []).map((r, i) => /*#__PURE__*/React.createElement("div", {
          key: i,
          style: {
            display: "flex",
            justifyContent: "space-between",
            padding: "6px 12px",
            borderTop: i ? "1px solid hsl(var(--border))" : "none",
            fontSize: 12,
            color: "hsl(var(--foreground))"
          }
        }, /*#__PURE__*/React.createElement("span", null, r[0]), /*#__PURE__*/React.createElement("span", {
          style: {
            fontFamily: "var(--font-mono)",
            color: "hsl(var(--muted-foreground))"
          }
        }, r[1]))));
      case "metric":
        return /*#__PURE__*/React.createElement("div", {
          style: {
            padding: "14px 14px 16px"
          }
        }, /*#__PURE__*/React.createElement("div", {
          style: {
            fontFamily: "var(--font-mono)",
            fontSize: 30,
            fontWeight: 600,
            color: "hsl(var(--foreground))",
            lineHeight: 1
          }
        }, w.value || "37"), /*#__PURE__*/React.createElement("div", {
          style: {
            fontSize: 11,
            color: "hsl(var(--muted-foreground))",
            marginTop: 4
          }
        }, w.caption || "active memories · +4 today"), /*#__PURE__*/React.createElement("div", {
          style: {
            display: "flex",
            gap: 3,
            marginTop: 12,
            alignItems: "flex-end",
            height: 34
          }
        }, (w.spark || [8, 12, 9, 15, 11, 18, 14, 22, 19, 26, 21, 28]).map((v, i) => /*#__PURE__*/React.createElement("span", {
          key: i,
          style: {
            flex: 1,
            height: v / 28 * 100 + "%",
            background: "hsl(var(--primary) / " + (0.35 + i / 22) + ")",
            borderRadius: 2
          }
        }))));
      case "weather":
        return /*#__PURE__*/React.createElement("div", {
          style: {
            padding: "12px 14px"
          }
        }, /*#__PURE__*/React.createElement("div", {
          style: {
            display: "flex",
            alignItems: "center",
            gap: 10
          }
        }, /*#__PURE__*/React.createElement(Icon, {
          name: "cloud-sun",
          size: 30,
          color: "hsl(var(--warning))"
        }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
          style: {
            fontFamily: "var(--font-mono)",
            fontSize: 24,
            fontWeight: 600,
            color: "hsl(var(--foreground))"
          }
        }, w.temp || "19°"), /*#__PURE__*/React.createElement("div", {
          style: {
            fontSize: 11,
            color: "hsl(var(--muted-foreground))"
          }
        }, w.place || "Lisbon · clear"))));
      default:
        return null;
    }
  };
  const bodyH = bodyRef.current ? bodyRef.current.clientHeight : 500;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      width: 400,
      borderLeft: "1px solid hsl(var(--border))",
      background: "hsl(var(--background))",
      flexShrink: 0,
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      borderBottom: "1px solid hsl(var(--border))",
      height: 52,
      padding: "0 12px",
      flexShrink: 0,
      position: "relative"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "layout-grid",
    size: 15,
    color: "hsl(var(--primary))"
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      fontSize: 13,
      fontWeight: 600,
      color: "hsl(var(--foreground))"
    }
  }, "Canvas"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 10,
      color: "hsl(var(--muted-foreground))"
    }
  }, widgets.length), /*#__PURE__*/React.createElement(IconButton, {
    size: "sm",
    title: "Tidy layout",
    onClick: tidy
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "layout-dashboard",
    size: 15
  })), /*#__PURE__*/React.createElement(IconButton, {
    size: "sm",
    active: menuOpen,
    title: "Add widget",
    onClick: () => setMenuOpen(v => !v)
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "plus",
    size: 15
  })), /*#__PURE__*/React.createElement(IconButton, {
    size: "sm",
    title: "Collapse",
    onClick: onToggle
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "panel-right-close",
    size: 15
  })), menuOpen && /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      top: "100%",
      right: 8,
      zIndex: 40,
      marginTop: 4,
      minWidth: 172,
      borderRadius: "var(--radius-md)",
      border: "1px solid hsl(var(--border))",
      background: "hsl(var(--popover))",
      boxShadow: "var(--shadow-lg)",
      overflow: "hidden"
    }
  }, ADDABLE.map(a => /*#__PURE__*/React.createElement("button", {
    key: a.type,
    onClick: () => {
      onAdd(a.type, a.title);
      setMenuOpen(false);
    },
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      width: "100%",
      padding: "8px 12px",
      border: "none",
      background: "transparent",
      cursor: "pointer",
      color: "hsl(var(--foreground))",
      fontSize: 12,
      fontFamily: "var(--font-sans)",
      textAlign: "left"
    },
    onMouseEnter: e => e.currentTarget.style.background = "hsl(var(--surface-hover))",
    onMouseLeave: e => e.currentTarget.style.background = "transparent"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: a.icon,
    size: 14,
    color: "hsl(var(--muted-foreground))"
  }), a.title)))), /*#__PURE__*/React.createElement("div", {
    ref: bodyRef,
    style: {
      flex: 1,
      minHeight: 0,
      overflow: expandedId ? "hidden" : "auto",
      position: "relative"
    }
  }, widgets.length === 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: "center",
      color: "hsl(var(--muted-foreground))",
      fontSize: 12,
      padding: "48px 16px"
    }
  }, "Empty canvas. Add a widget, or ask Cowork to build one."), widgets.map(w => {
    const l = layout[w.id];
    if (!l) return null;
    const isExp = expandedId === w.id;
    if (expandedId && !isExp) return null;
    const wrap = isExp ? {
      position: "absolute",
      left: 12,
      top: 12,
      right: 12,
      bottom: 12,
      zIndex: 50
    } : {
      position: "absolute",
      left: l.x,
      top: l.y,
      width: l.w,
      height: l.h,
      zIndex: zmap[w.id] || 1
    };
    const innerH = (isExp ? bodyH - 24 : l.h) - 38 - (w.footer ? 28 : 0);
    return /*#__PURE__*/React.createElement("div", {
      key: w.id,
      className: w.justAdded ? "pa-widget-in" : "",
      style: wrap
    }, /*#__PURE__*/React.createElement(CanvasWidget, {
      fill: true,
      title: w.title,
      generated: w.generated,
      icon: /*#__PURE__*/React.createElement(Icon, {
        name: w.icon || "square",
        size: 14
      }),
      footer: w.footer,
      expanded: isExp,
      onExpand: () => setExpandedId(x => x === w.id ? null : w.id),
      onClose: () => onRemove(w.id),
      onRefresh: () => {},
      dragHandleProps: {
        onPointerDown: startDrag(w.id)
      },
      resizeHandleProps: {
        onPointerDown: startResize(w.id)
      }
    }, body(w, Math.max(80, innerH))));
  })));
}
function defaultH(type) {
  return {
    "memory-graph": 240,
    "memory-hex": 260,
    plan: 168,
    diff: 208,
    table: 168,
    metric: 180,
    weather: 120
  }[type] || 180;
}
const DEFAULT_PLAN = [{
  text: "Scan session for new facts",
  status: "done"
}, {
  text: "Cluster micro-memories",
  status: "active"
}, {
  text: "Promote cluster → macro",
  status: "pending"
}];
const DEFAULT_DIFF = `@@ -8,3 +8,4 @@ class HMGGraph
   constructor() {
-    this.nodes = [];
+    this.nodes = new Map();
+    this.macros = new Map();
   }`;
window.CoworkCanvas = CoworkCanvas;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/cowork/Canvas.jsx", error: String((e && e.message) || e) }); }

// ui_kits/cowork/CoworkApp.jsx
try { (() => {
/* Cowork — app orchestrator: login → 3-pane (rail · transcript · canvas), theme, flows. */
function CoworkLogin({
  theme,
  onAuth
}) {
  const {
    Input,
    Button
  } = window.PersonalAgentDesignSystem_94ad89;
  const {
    Icon
  } = window.PA;
  const [t, setT] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const submit = e => {
    e.preventDefault();
    if (!t.trim()) return;
    setLoading(true);
    setTimeout(onAuth, 600);
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      height: "100%",
      width: "100%",
      alignItems: "center",
      justifyContent: "center",
      background: "hsl(var(--background))",
      backgroundImage: "radial-gradient(120% 80% at 50% -10%, hsl(var(--primary) / 0.10), transparent 55%)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 350,
      padding: "0 16px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      gap: 14,
      marginBottom: 26
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      height: 56,
      width: 56,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 18,
      background: "hsl(var(--primary) / 0.14)",
      border: "1px solid hsl(var(--primary) / 0.25)"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "bot",
    size: 28,
    color: "hsl(var(--primary))"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: "center"
    }
  }, /*#__PURE__*/React.createElement("h1", {
    style: {
      margin: 0,
      fontSize: 22,
      fontWeight: 700,
      color: "hsl(var(--foreground))",
      letterSpacing: "-0.02em"
    }
  }, "Cowork"), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: "6px 0 0",
      fontSize: 13,
      color: "hsl(var(--muted-foreground))"
    }
  }, "Your personal agent, with a memory that never forgets."))), /*#__PURE__*/React.createElement("form", {
    onSubmit: submit,
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(Input, {
    leftIcon: /*#__PURE__*/React.createElement(Icon, {
      name: "key-round",
      size: 16
    }),
    type: "password",
    value: t,
    onChange: e => setT(e.target.value),
    placeholder: "Access token",
    autoFocus: true
  }), /*#__PURE__*/React.createElement(Button, {
    type: "submit",
    disabled: loading || !t.trim(),
    rightIcon: !loading && /*#__PURE__*/React.createElement(Icon, {
      name: "arrow-right",
      size: 16
    }),
    style: {
      width: "100%"
    }
  }, loading ? "Connecting…" : "Enter workspace")), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 11,
      color: "hsl(var(--primary))",
      textAlign: "center",
      marginTop: 16,
      opacity: 0.85
    }
  }, "Demo \u2014 type anything and continue.")));
}
function CoworkApp() {
  const [authed, setAuthed] = React.useState(false);
  const [theme, setTheme] = React.useState("pa-cowork-dark");
  const [railOpen, setRailOpen] = React.useState(true);
  const [canvasOpen, setCanvasOpen] = React.useState(true);
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const [provider, setProvider] = React.useState("claude_code");
  const [streaming, setStreaming] = React.useState(false);
  const toggleTheme = () => setTheme(t => t.indexOf("dark") >= 0 ? "pa-cowork-light" : "pa-cowork-dark");
  const [sessions, setSessions] = React.useState([{
    id: "s1",
    title: "HMG memory tuning",
    msgs: 46,
    ago: "2m ago",
    status: "working",
    pinned: true,
    group: "Personal Agent"
  }, {
    id: "s2",
    title: "Trip to Lisbon",
    msgs: 12,
    ago: "1h ago",
    status: "done",
    group: "Personal"
  }, {
    id: "s3",
    title: "Refactor macro compression",
    msgs: 28,
    ago: "3h ago",
    status: "active",
    group: "Personal Agent"
  }, {
    id: "s4",
    title: "Weekly review",
    msgs: 9,
    ago: "1d ago"
  }, {
    id: "s5",
    title: "Cello practice log",
    msgs: 5,
    ago: "2d ago",
    group: "Personal"
  }]);
  const [groups, setGroups] = React.useState(["Personal Agent", "Personal"]);
  const [activeId, setActiveId] = React.useState("s1");
  const newGroup = name => {
    const n = (name || "").trim();
    if (n && !groups.includes(n)) setGroups(g => [...g, n]);
  };
  const assignGroup = (id, group) => {
    if (group && !groups.includes(group)) setGroups(g => [...g, group]);
    setSessions(ss => ss.map(s => s.id === id ? {
      ...s,
      group: group || undefined
    } : s));
  };
  const [messages, setMessages] = React.useState([{
    id: "m1",
    kind: "user",
    text: "Refactor the HMG graph to use Maps and show me what changed.",
    time: "2:11 PM"
  }, {
    id: "m2",
    kind: "thinking",
    text: "Planning refactor"
  }, {
    id: "m3",
    kind: "plan",
    title: "Refactor HMGGraph",
    steps: [{
      text: "Switch node/edge stores to Map",
      status: "done"
    }, {
      text: "Add macros index",
      status: "done"
    }, {
      text: "Update addPoint / recall",
      status: "active"
    }, {
      text: "Run memory tests",
      status: "pending"
    }]
  }, {
    id: "m4",
    kind: "tool",
    tool: {
      command: "rg -n 'this.nodes' src/memory",
      status: "success",
      duration: "0.3s",
      exitCode: 0,
      defaultOpen: false,
      output: "src/memory/hmg.ts:9:  this.nodes = [];\nsrc/memory/hmg.ts:41:  this.nodes.push(p);"
    }
  }, {
    id: "m5",
    kind: "diff",
    filename: "src/memory/hmg.ts",
    diff: "@@ -8,4 +8,5 @@ class HMGGraph\n   constructor() {\n-    this.nodes = [];\n-    this.edges = [];\n+    this.nodes = new Map();\n+    this.edges = new Map();\n+    this.macros = new Map();\n   }"
  }, {
    id: "m6",
    kind: "tool",
    tool: {
      command: "bun test memory",
      status: "success",
      duration: "1.9s",
      exitCode: 0,
      output: "✓ hmg: adds points\n✓ hmg: compresses cluster → macro\n✓ hmg: wormhole across biomes\n\n3 pass  0 fail"
    }
  }, {
    id: "m7",
    kind: "assistant",
    text: "Done. `HMGGraph` now uses `Map`s for nodes, edges and a new `macros` index — O(1) lookups and cleaner compression. All 3 memory tests pass. The diff is above and pinned to the canvas."
  }]);
  const [widgets, setWidgets] = React.useState([{
    id: "w1",
    type: "memory-graph",
    title: "Memory · Graph",
    icon: "network"
  }, {
    id: "w2",
    type: "plan",
    title: "Active plan",
    icon: "list-todo"
  }, {
    id: "w3",
    type: "diff",
    title: "src/memory/hmg.ts",
    icon: "file-diff",
    filename: "src/memory/hmg.ts"
  }]);
  const wid = React.useRef(10);
  const addWidget = (type, title, extra) => {
    const id = "w" + wid.current++;
    setWidgets(ws => [...ws, {
      id,
      type,
      title,
      icon: iconFor(type),
      justAdded: true,
      ...extra
    }]);
    setTimeout(() => setWidgets(ws => ws.map(w => w.id === id ? {
      ...w,
      justAdded: false
    } : w)), 500);
  };
  const removeWidget = id => setWidgets(ws => ws.filter(w => w.id !== id));

  // scripted "agent generates a widget" library
  const GEN = [{
    type: "weather",
    title: "Weather · Lisbon",
    footer: "✦ generated from your message",
    temp: "19°",
    place: "Lisbon · clear"
  }, {
    type: "table",
    title: "Lisbon budget",
    footer: "✦ generated",
    rows: [["Flights", "€240"], ["Stay · 3n", "€330"], ["Food", "€150"], ["Total", "€720"]]
  }, {
    type: "metric",
    title: "Memory density",
    footer: "✦ live",
    value: "0.68",
    caption: "avg ρ · rising"
  }];
  const genIdx = React.useRef(0);
  const send = text => {
    const uid = "u" + Date.now();
    setMessages(m => [...m, {
      id: uid,
      kind: "user",
      text,
      time: "now"
    }]);
    setStreaming(true);
    setTimeout(() => setMessages(m => [...m, {
      id: "th" + Date.now(),
      kind: "thinking",
      text: "Thinking"
    }]), 300);
    setTimeout(() => setMessages(m => [...m, {
      id: "tl" + Date.now(),
      kind: "tool",
      tool: {
        command: "recall '" + text.slice(0, 22) + "'",
        status: "success",
        duration: "0.2s",
        exitCode: 0,
        output: "3 memories recalled · 1 macro hit"
      }
    }]), 700);
    setTimeout(() => {
      const g = GEN[genIdx.current % GEN.length];
      genIdx.current++;
      addWidget(g.type, g.title, {
        generated: true,
        footer: g.footer,
        temp: g.temp,
        place: g.place,
        rows: g.rows,
        value: g.value,
        caption: g.caption
      });
      setCanvasOpen(true);
    }, 1100);
    setTimeout(() => {
      setMessages(m => [...m, {
        id: "a" + Date.now(),
        kind: "assistant",
        text: "Here's what I found — I also spun up a widget on the canvas so you can keep it in view. Want me to save it to memory?"
      }]);
      setStreaming(false);
    }, 1500);
  };
  const activeTitle = sessions.find(s => s.id === activeId)?.title || "Cowork";
  const modelLabel = provider === "claude_code" ? "claude-cli" : provider;
  return /*#__PURE__*/React.createElement("div", {
    className: theme,
    style: {
      height: "100%",
      width: "100%"
    }
  }, !authed ? /*#__PURE__*/React.createElement(CoworkLogin, {
    theme: theme,
    onAuth: () => setAuthed(true)
  }) : /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      display: "flex",
      height: "100%",
      width: "100%",
      background: "hsl(var(--background))",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement(CoworkRail, {
    sessions: sessions,
    activeId: activeId,
    onSelect: setActiveId,
    onNew: () => {},
    groups: groups,
    onNewGroup: newGroup,
    onAssignGroup: assignGroup,
    onOpenSettings: () => setSettingsOpen(true),
    theme: theme,
    onToggleTheme: toggleTheme,
    open: railOpen,
    onToggle: () => setRailOpen(o => !o)
  }), /*#__PURE__*/React.createElement(CoworkTranscript, {
    title: activeTitle,
    model: modelLabel,
    messages: messages,
    onSend: send,
    streaming: streaming,
    canvasOpen: canvasOpen,
    onToggleCanvas: () => setCanvasOpen(o => !o),
    railOpen: railOpen,
    onToggleRail: () => setRailOpen(o => !o)
  }), /*#__PURE__*/React.createElement(CoworkCanvas, {
    widgets: widgets,
    onRemove: removeWidget,
    onAdd: (type, title) => addWidget(type, title),
    open: canvasOpen,
    onToggle: () => setCanvasOpen(o => !o)
  }), /*#__PURE__*/React.createElement(CoworkSettings, {
    open: settingsOpen,
    onClose: () => setSettingsOpen(false),
    theme: theme,
    onToggleTheme: toggleTheme,
    provider: provider,
    onProvider: setProvider
  })));
}
function iconFor(type) {
  return {
    "memory-graph": "network",
    "memory-hex": "hexagon",
    plan: "list-todo",
    diff: "file-diff",
    table: "table",
    metric: "activity",
    weather: "cloud-sun"
  }[type] || "square";
}
window.CoworkApp = CoworkApp;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/cowork/CoworkApp.jsx", error: String((e && e.message) || e) }); }

// ui_kits/cowork/Rail.jsx
try { (() => {
/* Cowork — left sessions rail with chat GROUPS (warm restyle). */
function CoworkSessionItem({
  s,
  active,
  groups,
  onSelect,
  onAssign
}) {
  const {
    SessionRow
  } = window.PersonalAgentDesignSystem_94ad89;
  const {
    Icon
  } = window.PA;
  const [menu, setMenu] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const h = e => {
      if (ref.current && !ref.current.contains(e.target)) setMenu(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const item = on => ({
    display: "flex",
    alignItems: "center",
    gap: 7,
    width: "100%",
    padding: "6px 8px",
    border: "none",
    background: on ? "hsl(var(--primary) / 0.1)" : "transparent",
    color: on ? "hsl(var(--primary))" : "hsl(var(--foreground))",
    fontSize: 12,
    fontFamily: "var(--font-sans)",
    cursor: "pointer",
    borderRadius: 6,
    textAlign: "left"
  });
  return /*#__PURE__*/React.createElement("div", {
    ref: ref,
    style: {
      position: "relative"
    },
    onContextMenu: e => {
      e.preventDefault();
      setMenu(true);
    }
  }, /*#__PURE__*/React.createElement(SessionRow, {
    active: active,
    pinned: s.pinned,
    title: s.title,
    meta: `${s.msgs} msgs · ${s.ago}`,
    status: s.status,
    onClick: () => onSelect(s.id)
  }), menu && /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      right: 6,
      top: 26,
      zIndex: 60,
      minWidth: 158,
      borderRadius: "var(--radius-md)",
      border: "1px solid hsl(var(--border))",
      background: "hsl(var(--popover))",
      boxShadow: "var(--shadow-lg)",
      overflow: "hidden",
      padding: 4
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9,
      fontWeight: 600,
      textTransform: "uppercase",
      letterSpacing: "0.05em",
      color: "hsl(var(--muted-foreground))",
      padding: "3px 8px"
    }
  }, "Move to group"), groups.map(g => /*#__PURE__*/React.createElement("button", {
    key: g,
    onClick: () => {
      onAssign(s.id, g);
      setMenu(false);
    },
    style: item(s.group === g),
    onMouseEnter: e => {
      if (s.group !== g) e.currentTarget.style.background = "hsl(var(--surface-hover))";
    },
    onMouseLeave: e => {
      if (s.group !== g) e.currentTarget.style.background = "transparent";
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "folder",
    size: 12
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }, g), s.group === g && /*#__PURE__*/React.createElement(Icon, {
    name: "check",
    size: 12
  }))), s.group && /*#__PURE__*/React.createElement("button", {
    onClick: () => {
      onAssign(s.id, "");
      setMenu(false);
    },
    style: item(false),
    onMouseEnter: e => e.currentTarget.style.background = "hsl(var(--surface-hover))",
    onMouseLeave: e => e.currentTarget.style.background = "transparent"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "folder-minus",
    size: 12
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }, "Remove from group"))));
}
function CoworkRail({
  sessions,
  groups = [],
  activeId,
  onSelect,
  onNew,
  onNewGroup,
  onAssignGroup,
  onOpenSettings,
  theme,
  onToggleTheme,
  open,
  onToggle
}) {
  const {
    IconButton,
    Input,
    Button
  } = window.PersonalAgentDesignSystem_94ad89;
  const {
    Icon
  } = window.PA;
  const [q, setQ] = React.useState("");
  const [collapsed, setCollapsed] = React.useState({});
  const [creating, setCreating] = React.useState(false);
  const [newName, setNewName] = React.useState("");
  const isDark = theme.indexOf("dark") >= 0;
  const toggleGroup = g => setCollapsed(c => ({
    ...c,
    [g]: !c[g]
  }));
  if (!open) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
        width: 52,
        borderRight: "1px solid hsl(var(--border))",
        background: "hsl(var(--sidebar-background))",
        padding: "12px 0",
        flexShrink: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        height: 30,
        width: 30,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: "var(--radius-md)",
        background: "hsl(var(--primary) / 0.14)",
        marginBottom: 4
      }
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "bot",
      size: 17,
      color: "hsl(var(--primary))"
    })), /*#__PURE__*/React.createElement(IconButton, {
      title: "Open",
      onClick: onToggle
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "chevron-right"
    })), /*#__PURE__*/React.createElement(IconButton, {
      title: "New chat",
      onClick: onNew
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "plus"
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }), /*#__PURE__*/React.createElement(IconButton, {
      title: isDark ? "Light" : "Dark",
      onClick: onToggleTheme
    }, /*#__PURE__*/React.createElement(Icon, {
      name: isDark ? "sun" : "moon",
      size: 16
    })), /*#__PURE__*/React.createElement(IconButton, {
      title: "Settings",
      onClick: onOpenSettings
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "settings",
      size: 16
    })));
  }
  const match = s => s.title.toLowerCase().includes(q.toLowerCase());
  const ungrouped = sessions.filter(s => !s.group && match(s));
  const commitGroup = () => {
    if (newName.trim()) {
      onNewGroup(newName.trim());
    }
    setNewName("");
    setCreating(false);
  };
  const label = {
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: "0.05em",
    textTransform: "uppercase",
    color: "hsl(var(--muted-foreground))"
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      width: 248,
      borderRight: "1px solid hsl(var(--border))",
      background: "hsl(var(--sidebar-background))",
      flexShrink: 0,
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      height: 52,
      padding: "0 12px",
      borderBottom: "1px solid hsl(var(--border))",
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: 28,
      width: 28,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      borderRadius: "var(--radius-md)",
      background: "hsl(var(--primary) / 0.14)"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "bot",
    size: 16,
    color: "hsl(var(--primary))"
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      fontSize: 14,
      fontWeight: 700,
      color: "hsl(var(--foreground))",
      letterSpacing: "-0.01em"
    }
  }, "Cowork"), /*#__PURE__*/React.createElement(IconButton, {
    size: "sm",
    title: "Collapse",
    onClick: onToggle
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "chevron-left"
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "10px 10px 8px"
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    onClick: onNew,
    leftIcon: /*#__PURE__*/React.createElement(Icon, {
      name: "plus",
      size: 15
    }),
    style: {
      width: "100%",
      height: 34,
      fontSize: 13,
      justifyContent: "flex-start",
      gap: 8
    }
  }, "New chat")), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "0 10px 8px"
    }
  }, /*#__PURE__*/React.createElement(Input, {
    surface: "flush",
    leftIcon: /*#__PURE__*/React.createElement(Icon, {
      name: "search",
      size: 14
    }),
    value: q,
    onChange: e => setQ(e.target.value),
    placeholder: "Search",
    style: {
      height: 32,
      fontSize: 12,
      paddingLeft: 32
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflowY: "auto",
      padding: "0 6px 6px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      padding: "4px 6px 4px"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      ...label,
      flex: 1
    }
  }, "Groups"), /*#__PURE__*/React.createElement("button", {
    onClick: () => setCreating(v => !v),
    title: "New group",
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 3,
      border: "none",
      background: "transparent",
      color: "hsl(var(--muted-foreground))",
      cursor: "pointer",
      fontSize: 10,
      fontWeight: 600
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "folder-plus",
    size: 12
  }), " New")), creating && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "0 6px 6px"
    }
  }, /*#__PURE__*/React.createElement("input", {
    autoFocus: true,
    value: newName,
    onChange: e => setNewName(e.target.value),
    onKeyDown: e => {
      if (e.key === "Enter") commitGroup();
      if (e.key === "Escape") {
        setCreating(false);
        setNewName("");
      }
    },
    onBlur: commitGroup,
    placeholder: "Group name\u2026",
    style: {
      width: "100%",
      height: 28,
      padding: "0 10px",
      fontFamily: "var(--font-sans)",
      fontSize: 12,
      color: "hsl(var(--foreground))",
      background: "hsl(var(--background))",
      border: "1px solid hsl(var(--primary))",
      borderRadius: "var(--radius-sm)",
      outline: "none"
    }
  })), groups.map(g => {
    const items = sessions.filter(s => s.group === g && match(s));
    const col = collapsed[g];
    return /*#__PURE__*/React.createElement("div", {
      key: g,
      style: {
        marginBottom: 2
      }
    }, /*#__PURE__*/React.createElement("button", {
      onClick: () => toggleGroup(g),
      style: {
        display: "flex",
        alignItems: "center",
        gap: 6,
        width: "100%",
        padding: "5px 8px",
        border: "none",
        background: "transparent",
        cursor: "pointer",
        ...label
      }
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "chevron-down",
      size: 11,
      style: {
        transform: col ? "rotate(-90deg)" : "none",
        transition: "transform .15s"
      }
    }), /*#__PURE__*/React.createElement(Icon, {
      name: "folder",
      size: 12,
      color: "hsl(var(--primary))"
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1,
        textAlign: "left"
      }
    }, g), /*#__PURE__*/React.createElement("span", {
      style: {
        opacity: .7
      }
    }, items.length)), !col && items.map(s => /*#__PURE__*/React.createElement(CoworkSessionItem, {
      key: s.id,
      s: s,
      active: s.id === activeId,
      groups: groups,
      onSelect: onSelect,
      onAssign: onAssignGroup
    })), !col && items.length === 0 && /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 11,
        color: "hsl(var(--muted-foreground))",
        padding: "2px 8px 4px 26px",
        fontStyle: "italic"
      }
    }, "empty \xB7 right-click a chat to add"));
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      ...label,
      padding: "8px 8px 4px"
    }
  }, "Recent"), ungrouped.map(s => /*#__PURE__*/React.createElement(CoworkSessionItem, {
    key: s.id,
    s: s,
    active: s.id === activeId,
    groups: groups,
    onSelect: onSelect,
    onAssign: onAssignGroup
  })), ungrouped.length === 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: "hsl(var(--muted-foreground))",
      padding: "2px 8px"
    }
  }, "\u2014"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: "hsl(var(--muted-foreground))",
      padding: "8px 8px 2px",
      opacity: .7
    }
  }, "Right-click a chat to move it to a group.")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 4,
      borderTop: "1px solid hsl(var(--border))",
      padding: "8px 10px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: 26,
      width: 26,
      borderRadius: 999,
      background: "hsl(var(--surface-3))",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontSize: 11,
      fontWeight: 600,
      color: "hsl(var(--foreground))"
    }
  }, "C"), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      fontSize: 12,
      color: "hsl(var(--foreground))"
    }
  }, "Chris"), /*#__PURE__*/React.createElement(IconButton, {
    size: "sm",
    title: isDark ? "Light mode" : "Dark mode",
    onClick: onToggleTheme
  }, /*#__PURE__*/React.createElement(Icon, {
    name: isDark ? "sun" : "moon",
    size: 15
  })), /*#__PURE__*/React.createElement(IconButton, {
    size: "sm",
    title: "Settings",
    onClick: onOpenSettings
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "settings",
    size: 15
  }))));
}
window.CoworkRail = CoworkRail;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/cowork/Rail.jsx", error: String((e && e.message) || e) }); }

// ui_kits/cowork/Settings.jsx
try { (() => {
/* Cowork — Settings overlay: connectors, model, appearance. */
function CoworkSettings({
  open,
  onClose,
  theme,
  onToggleTheme,
  provider,
  onProvider
}) {
  const {
    IconButton,
    ProviderSelect,
    Badge,
    Button
  } = window.PersonalAgentDesignSystem_94ad89;
  const {
    Icon
  } = window.PA;
  if (!open) return null;
  const isDark = theme.indexOf("dark") >= 0;
  const CONNECTORS = [{
    name: "Google",
    icon: "mail",
    desc: "Gmail · Calendar · Drive",
    on: true,
    scopes: ["email", "calendar", "drive"]
  }, {
    name: "GitHub",
    icon: "github",
    desc: "Repos · issues · PRs",
    on: true,
    scopes: ["repo", "read:org"]
  }, {
    name: "Slack",
    icon: "slack",
    desc: "Messages · channels",
    on: false
  }, {
    name: "Filesystem",
    icon: "folder",
    desc: "~/personal-agent",
    on: true
  }, {
    name: "Web search",
    icon: "globe",
    desc: "Brave Search API",
    on: true
  }];
  const PROVIDERS = [{
    id: "codex",
    label: "Codex",
    free: true
  }, {
    id: "claude_code",
    label: "Claude CLI",
    free: true
  }, {
    id: "anthropic",
    label: "Anthropic"
  }, {
    id: "openai",
    label: "OpenAI"
  }, {
    id: "ollama",
    label: "Ollama"
  }];
  const Section = ({
    title,
    children
  }) => /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 22
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      fontWeight: 600,
      letterSpacing: "0.05em",
      textTransform: "uppercase",
      color: "hsl(var(--muted-foreground))",
      marginBottom: 10
    }
  }, title), children);
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClose,
    style: {
      position: "absolute",
      inset: 0,
      zIndex: 60,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "hsl(0 0% 0% / 0.5)",
      backdropFilter: "blur(3px)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      width: 520,
      maxWidth: "92%",
      maxHeight: "86%",
      overflow: "auto",
      borderRadius: "var(--radius-lg)",
      border: "1px solid hsl(var(--border))",
      background: "hsl(var(--popover))",
      boxShadow: "var(--shadow-xl)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      padding: "14px 16px",
      borderBottom: "1px solid hsl(var(--border))",
      position: "sticky",
      top: 0,
      background: "hsl(var(--popover))"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "settings",
    size: 16,
    color: "hsl(var(--primary))"
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      fontSize: 15,
      fontWeight: 600,
      color: "hsl(var(--foreground))"
    }
  }, "Settings"), /*#__PURE__*/React.createElement(IconButton, {
    size: "sm",
    title: "Close",
    onClick: onClose
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "x",
    size: 16
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 16
    }
  }, /*#__PURE__*/React.createElement(Section, {
    title: "Appearance"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8
    }
  }, [{
    id: "light",
    label: "Light",
    icon: "sun"
  }, {
    id: "dark",
    label: "Dark",
    icon: "moon"
  }].map(m => {
    const active = m.id === "dark" === isDark;
    return /*#__PURE__*/React.createElement("button", {
      key: m.id,
      onClick: () => {
        if (!active) onToggleTheme();
      },
      style: {
        flex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        padding: "10px",
        borderRadius: "var(--radius-md)",
        cursor: "pointer",
        border: `1px solid ${active ? "hsl(var(--primary))" : "hsl(var(--border))"}`,
        background: active ? "hsl(var(--primary) / 0.1)" : "transparent",
        color: active ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))",
        fontSize: 13,
        fontWeight: 500,
        fontFamily: "var(--font-sans)"
      }
    }, /*#__PURE__*/React.createElement(Icon, {
      name: m.icon,
      size: 15
    }), m.label);
  }))), /*#__PURE__*/React.createElement(Section, {
    title: "Model"
  }, /*#__PURE__*/React.createElement(ProviderSelect, {
    options: PROVIDERS,
    value: provider,
    onChange: onProvider,
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "cpu",
      size: 14
    })
  })), /*#__PURE__*/React.createElement(Section, {
    title: "Connectors"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 8
    }
  }, CONNECTORS.map(c => /*#__PURE__*/React.createElement("div", {
    key: c.name,
    style: {
      display: "flex",
      alignItems: "center",
      gap: 10,
      padding: "10px 12px",
      borderRadius: "var(--radius-md)",
      border: "1px solid hsl(var(--border))",
      background: "hsl(var(--surface-2))"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: 30,
      width: 30,
      borderRadius: "var(--radius-sm)",
      background: "hsl(var(--surface-3))",
      display: "flex",
      alignItems: "center",
      justifyContent: "center"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: c.icon,
    size: 15,
    color: "hsl(var(--foreground))"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 13,
      fontWeight: 600,
      color: "hsl(var(--foreground))"
    }
  }, c.name), c.scopes && c.on && c.scopes.map(s => /*#__PURE__*/React.createElement("span", {
    key: s,
    style: {
      fontSize: 9,
      color: "hsl(var(--muted-foreground))",
      border: "1px solid hsl(var(--border))",
      borderRadius: 999,
      padding: "0 5px"
    }
  }, s))), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: "hsl(var(--muted-foreground))",
      marginTop: 1
    }
  }, c.desc)), c.on ? /*#__PURE__*/React.createElement(Badge, {
    tone: "emerald"
  }, "connected") : /*#__PURE__*/React.createElement(Button, {
    size: "sm",
    variant: "outline",
    style: {
      height: 28,
      fontSize: 12
    }
  }, "Connect"))))))));
}
window.CoworkSettings = CoworkSettings;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/cowork/Settings.jsx", error: String((e && e.message) || e) }); }

// ui_kits/cowork/Transcript.jsx
try { (() => {
/* Cowork — center transcript: chat + inline tool blocks, plan, diff, composer. */
function CoworkTranscript({
  title,
  model,
  messages,
  onSend,
  streaming,
  canvasOpen,
  onToggleCanvas,
  railOpen,
  onToggleRail
}) {
  const {
    MessageBubble,
    ToolCallBlock,
    PlanTracker,
    DiffView,
    Pill,
    IconButton,
    Badge
  } = window.PersonalAgentDesignSystem_94ad89;
  const {
    Icon
  } = window.PA;
  const [text, setText] = React.useState("");
  const scrollRef = React.useRef(null);
  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, streaming]);
  const send = () => {
    if (!text.trim()) return;
    onSend(text.trim());
    setText("");
  };
  const onKey = e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };
  const renderMsg = m => {
    switch (m.kind) {
      case "user":
      case "assistant":
        return /*#__PURE__*/React.createElement(MessageBubble, {
          key: m.id,
          role: m.kind,
          timestamp: m.time
        }, m.text);
      case "thinking":
        return /*#__PURE__*/React.createElement("div", {
          key: m.id,
          style: {
            display: "flex",
            padding: "2px 20px"
          }
        }, /*#__PURE__*/React.createElement(Pill, {
          icon: /*#__PURE__*/React.createElement(Icon, {
            name: "brain",
            size: 12,
            color: "var(--thinking)"
          })
        }, m.text || "Thinking"));
      case "tool":
        return /*#__PURE__*/React.createElement("div", {
          key: m.id,
          style: {
            padding: "3px 20px"
          }
        }, /*#__PURE__*/React.createElement(ToolCallBlock, m.tool));
      case "plan":
        return /*#__PURE__*/React.createElement("div", {
          key: m.id,
          style: {
            padding: "5px 20px"
          }
        }, /*#__PURE__*/React.createElement(PlanTracker, {
          title: m.title,
          steps: m.steps
        }));
      case "diff":
        return /*#__PURE__*/React.createElement("div", {
          key: m.id,
          style: {
            padding: "5px 20px"
          }
        }, /*#__PURE__*/React.createElement(DiffView, {
          filename: m.filename,
          diff: m.diff
        }));
      default:
        return null;
    }
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      flex: 1,
      minWidth: 0,
      minHeight: 0,
      background: "hsl(var(--background))"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      borderBottom: "1px solid hsl(var(--border))",
      height: 52,
      padding: "0 14px",
      flexShrink: 0
    }
  }, !railOpen && /*#__PURE__*/React.createElement(IconButton, {
    title: "Sessions",
    onClick: onToggleRail
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "panel-left-open"
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 14,
      fontWeight: 600,
      color: "hsl(var(--foreground))",
      flex: 1,
      minWidth: 0,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
    }
  }, title), /*#__PURE__*/React.createElement(Badge, {
    tone: "neutral"
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)"
    }
  }, model))), /*#__PURE__*/React.createElement("div", {
    ref: scrollRef,
    style: {
      flex: 1,
      minHeight: 0,
      overflowY: "auto",
      padding: "16px 0"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 760,
      margin: "0 auto"
    }
  }, messages.map(renderMsg), streaming && /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      padding: "6px 20px",
      fontSize: 13,
      color: "hsl(var(--muted-foreground))",
      fontFamily: "var(--font-mono)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      height: 7,
      width: 7,
      borderRadius: 999,
      background: "hsl(var(--primary))",
      animation: "pa-pulse-glow 1.2s ease-in-out infinite"
    }
  }), "working", /*#__PURE__*/React.createElement("span", {
    className: "pa-caret",
    style: {
      color: "hsl(var(--primary))"
    }
  }, "\u258B")))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "0 14px 12px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 760,
      margin: "0 auto"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12,
      padding: "4px 4px 6px",
      fontFamily: "var(--font-mono)",
      fontSize: 10.5,
      color: "hsl(var(--muted-foreground))"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 4
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "git-branch",
    size: 11
  }), " main"), /*#__PURE__*/React.createElement("span", null, "~/personal-agent"), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: "auto",
      display: "inline-flex",
      alignItems: "center",
      gap: 4
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "circle",
    size: 8,
    color: "hsl(var(--status-done))"
  }), " ready"), /*#__PURE__*/React.createElement("span", null, "12.4k tok")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      borderRadius: "var(--radius-xl)",
      border: "1px solid hsl(var(--border))",
      background: "hsl(var(--surface-2))"
    }
  }, /*#__PURE__*/React.createElement("textarea", {
    value: text,
    onChange: e => setText(e.target.value),
    onKeyDown: onKey,
    rows: 1,
    placeholder: "Ask Cowork to build, recall, or run something\u2026",
    style: {
      width: "100%",
      resize: "none",
      background: "transparent",
      border: "none",
      outline: "none",
      padding: "12px 14px 4px",
      fontFamily: "var(--font-sans)",
      fontSize: 14,
      color: "hsl(var(--foreground))"
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "0 8px 8px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 2
    }
  }, /*#__PURE__*/React.createElement(IconButton, {
    title: "Attach"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "paperclip",
    size: 16
  })), /*#__PURE__*/React.createElement(IconButton, {
    title: "Add to canvas"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "layout-grid",
    size: 16
  }))), /*#__PURE__*/React.createElement("button", {
    onClick: send,
    disabled: !text.trim(),
    title: "Send",
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      height: 30,
      padding: "0 12px",
      borderRadius: "var(--radius-md)",
      border: "none",
      cursor: text.trim() ? "pointer" : "not-allowed",
      background: text.trim() ? "hsl(var(--primary))" : "hsl(var(--surface-3))",
      color: text.trim() ? "hsl(var(--primary-foreground))" : "hsl(var(--muted-foreground))",
      fontFamily: "var(--font-sans)",
      fontSize: 12,
      fontWeight: 600,
      transition: "background var(--dur-fast)"
    }
  }, "Send ", /*#__PURE__*/React.createElement(Icon, {
    name: "corner-down-left",
    size: 13
  })))))));
}
window.CoworkTranscript = CoworkTranscript;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/cowork/Transcript.jsx", error: String((e && e.message) || e) }); }

// ui_kits/personal-agent/App.jsx
try { (() => {
/* App — composes Login → 3-pane workspace, with a scripted demo conversation. */
function KitApp() {
  const [authed, setAuthed] = React.useState(false);
  const [leftOpen, setLeftOpen] = React.useState(true);
  const [rightOpen, setRightOpen] = React.useState(true);
  const [provider, setProvider] = React.useState("codex");
  const [streaming, setStreaming] = React.useState(false);
  const [sessions] = React.useState([{
    id: "s1",
    title: "HMG graph tuning",
    msgs: 42,
    ago: "3m ago",
    status: "working",
    pinned: true
  }, {
    id: "s2",
    title: "Q3 roadmap draft",
    msgs: 18,
    ago: "1h ago",
    status: "done"
  }, {
    id: "s3",
    title: "Lisbon trip planning",
    msgs: 7,
    ago: "4h ago",
    status: "active"
  }, {
    id: "s4",
    title: "Django migration bug",
    msgs: 31,
    ago: "2d ago"
  }, {
    id: "s5",
    title: "Cello practice log",
    msgs: 5,
    ago: "3d ago"
  }]);
  const [activeId, setActiveId] = React.useState("s1");
  const seed = [{
    id: "m1",
    kind: "text",
    role: "user",
    text: "What did I decide about deploys, and how's my memory graph looking?",
    time: "2:14 PM"
  }, {
    id: "m2",
    kind: "tools",
    items: [{
      icon: "brain",
      iconColor: "var(--thinking)",
      label: "Thinking"
    }, {
      icon: "search",
      label: "recall: deploy policy",
      mono: true
    }, {
      icon: "network",
      label: "hex-graph: 37 nodes",
      mono: true
    }]
  }, {
    id: "m3",
    kind: "text",
    role: "assistant",
    text: "You set a rule: no production deploys on Fridays — the weekend on-call gap makes them risky. It's linked in your memory to two past incidents (a Negative-biome cluster).\n\nYour graph has 37 active nodes across 3 biomes, with 9 wormhole bridges connecting emotionally-related memories across sessions. It's on the right — hover a node to trace its links."
  }];
  const [messages, setMessages] = React.useState(seed);
  const REPLIES = ["Logged. I've written that to memory and tagged it Positive — it'll surface next time the topic comes up.", "Done. I connected it to your existing 'roadmap' macro node, so related recalls will pull it in automatically.", "Got it — I filed that as an event marker on today's session layer. You'll see a new amber node appear in the graph."];
  const replyIdx = React.useRef(0);
  const handleSend = text => {
    const uid = "u" + Date.now();
    setMessages(m => [...m, {
      id: uid,
      kind: "text",
      role: "user",
      text,
      time: "now"
    }]);
    setStreaming(true);
    setTimeout(() => {
      setMessages(m => [...m, {
        id: "t" + Date.now(),
        kind: "tools",
        items: [{
          icon: "brain",
          iconColor: "var(--thinking)",
          label: "Thinking"
        }, {
          icon: "file-text",
          label: "write_file memory.db",
          mono: true
        }, {
          dot: "done",
          label: "saved"
        }]
      }]);
    }, 500);
    setTimeout(() => {
      setMessages(m => [...m, {
        id: "a" + Date.now(),
        kind: "text",
        role: "assistant",
        text: REPLIES[replyIdx.current % REPLIES.length],
        time: "now"
      }]);
      replyIdx.current++;
      setStreaming(false);
    }, 1300);
  };
  const activeTitle = sessions.find(s => s.id === activeId)?.title || "Personal Agent";
  if (!authed) return /*#__PURE__*/React.createElement(KitLogin, {
    onAuth: () => setAuthed(true)
  });
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      height: "100%",
      width: "100%",
      background: "hsl(var(--background))",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement(KitSidebar, {
    sessions: sessions,
    activeId: activeId,
    onSelect: setActiveId,
    onNew: () => {},
    provider: provider,
    onProvider: setProvider,
    open: leftOpen,
    onToggle: () => setLeftOpen(o => !o)
  }), /*#__PURE__*/React.createElement(KitChat, {
    title: activeTitle,
    provider: provider,
    model: provider === "codex" ? "gpt-5" : "",
    messages: messages,
    onSend: handleSend,
    streaming: streaming,
    leftOpen: leftOpen,
    rightOpen: rightOpen,
    onToggleLeft: () => setLeftOpen(o => !o),
    onToggleRight: () => setRightOpen(o => !o)
  }), /*#__PURE__*/React.createElement(KitRightPanel, {
    open: rightOpen,
    onToggle: () => setRightOpen(o => !o)
  }));
}
window.KitApp = KitApp;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/personal-agent/App.jsx", error: String((e && e.message) || e) }); }

// ui_kits/personal-agent/Chat.jsx
try { (() => {
/* Center Chat view — header, message stream (MessageBubble + tool Pills), composer. */
function KitChat({
  title,
  provider,
  model,
  messages,
  onSend,
  streaming,
  leftOpen,
  rightOpen,
  onToggleLeft,
  onToggleRight
}) {
  const {
    MessageBubble,
    Pill,
    IconButton,
    Badge
  } = window.PersonalAgentDesignSystem_94ad89;
  const {
    Icon
  } = window.PA;
  const [text, setText] = React.useState("");
  const scrollRef = React.useRef(null);
  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, streaming]);
  const send = () => {
    if (!text.trim()) return;
    onSend(text.trim());
    setText("");
  };
  const onKey = e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      flex: 1,
      minWidth: 0,
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 8,
      borderBottom: "1px solid hsl(var(--border))",
      background: "hsl(var(--surface-2))",
      padding: "8px 12px",
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement(IconButton, {
    title: "Toggle sessions",
    active: leftOpen,
    onClick: onToggleLeft
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "panel-left-open"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 14,
      fontWeight: 500,
      color: "hsl(var(--foreground))",
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
    }
  }, title), /*#__PURE__*/React.createElement(Badge, null, provider, model ? ` · ${model}` : "")), /*#__PURE__*/React.createElement(IconButton, {
    title: "Toggle right panel",
    active: rightOpen,
    onClick: onToggleRight
  }, /*#__PURE__*/React.createElement(Icon, {
    name: rightOpen ? "panel-right-close" : "panel-right-open"
  }))), /*#__PURE__*/React.createElement("div", {
    ref: scrollRef,
    style: {
      flex: 1,
      minHeight: 0,
      overflowY: "auto",
      padding: "16px 0"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 768,
      margin: "0 auto"
    }
  }, messages.map(m => {
    if (m.kind === "tools") {
      return /*#__PURE__*/React.createElement("div", {
        key: m.id,
        style: {
          display: "flex",
          flexWrap: "wrap",
          gap: 6,
          justifyContent: "center",
          padding: "6px 16px"
        }
      }, m.items.map((t, i) => /*#__PURE__*/React.createElement(Pill, {
        key: i,
        mono: t.mono,
        tone: t.tone,
        icon: t.icon ? /*#__PURE__*/React.createElement(Icon, {
          name: t.icon,
          size: 12,
          color: t.iconColor || "hsl(var(--primary))"
        }) : null,
        dot: t.dot,
        pulse: t.pulse
      }, t.label)));
    }
    return /*#__PURE__*/React.createElement(MessageBubble, {
      key: m.id,
      role: m.role,
      timestamp: m.time
    }, m.text);
  }), streaming && /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      padding: "8px 16px",
      fontSize: 14,
      color: "hsl(var(--muted-foreground))"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "brain",
    size: 16,
    color: "var(--thinking)"
  }), /*#__PURE__*/React.createElement("span", null, "Reasoning\u2026")))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "12px 16px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 768,
      margin: "0 auto",
      display: "flex",
      flexDirection: "column",
      borderRadius: "var(--radius-2xl)",
      border: "1px solid hsl(var(--border))",
      background: "hsl(var(--background))"
    }
  }, /*#__PURE__*/React.createElement("textarea", {
    value: text,
    onChange: e => setText(e.target.value),
    onKeyDown: onKey,
    rows: 1,
    placeholder: "Message your agent...",
    style: {
      width: "100%",
      resize: "none",
      background: "transparent",
      border: "none",
      outline: "none",
      padding: "12px 16px 4px",
      fontFamily: "var(--font-sans)",
      fontSize: 14,
      color: "hsl(var(--foreground))"
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "0 8px 8px"
    }
  }, /*#__PURE__*/React.createElement(IconButton, {
    title: "Attach"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "paperclip",
    size: 16
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 4
    }
  }, /*#__PURE__*/React.createElement(IconButton, {
    title: "Voice"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "mic",
    size: 16
  })), /*#__PURE__*/React.createElement("button", {
    onClick: send,
    disabled: !text.trim(),
    title: "Send",
    style: {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      height: 32,
      width: 32,
      borderRadius: "var(--radius-md)",
      border: "none",
      cursor: text.trim() ? "pointer" : "not-allowed",
      background: text.trim() ? "hsl(var(--primary))" : "transparent",
      color: text.trim() ? "hsl(var(--primary-foreground))" : "hsl(var(--muted-foreground))",
      transition: "background var(--dur-fast)"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "send",
    size: 14
  })))))));
}
window.KitChat = KitChat;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/personal-agent/Chat.jsx", error: String((e && e.message) || e) }); }

// ui_kits/personal-agent/Login.jsx
try { (() => {
/* Login screen — token gate. Uses Input + Button from the design system. */
function KitLogin({
  onAuth
}) {
  const {
    Input,
    Button
  } = window.PersonalAgentDesignSystem_94ad89;
  const {
    Icon
  } = window.PA;
  const [token, setToken] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const submit = e => {
    e.preventDefault();
    if (!token.trim()) return;
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      onAuth();
    }, 650);
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      height: "100%",
      width: "100%",
      alignItems: "center",
      justifyContent: "center",
      background: "hsl(var(--background))"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 340,
      padding: "0 16px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      gap: 16,
      marginBottom: 30
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      height: 64,
      width: 64,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: "var(--radius-2xl)",
      background: "hsl(var(--surface-2))",
      border: "1px solid hsl(var(--border))"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "bot",
    size: 32,
    color: "hsl(var(--primary))"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: "center"
    }
  }, /*#__PURE__*/React.createElement("h1", {
    style: {
      margin: 0,
      fontSize: 20,
      fontWeight: 700,
      color: "hsl(var(--foreground))"
    }
  }, "Personal Agent"), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: "6px 0 0",
      fontSize: 14,
      color: "hsl(var(--muted-foreground))"
    }
  }, "Enter your access token to connect"))), /*#__PURE__*/React.createElement("form", {
    onSubmit: submit,
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(Input, {
    leftIcon: /*#__PURE__*/React.createElement(Icon, {
      name: "key-round",
      size: 16
    }),
    type: "password",
    value: token,
    onChange: e => setToken(e.target.value),
    placeholder: "Paste your auth token...",
    autoFocus: true
  }), /*#__PURE__*/React.createElement(Button, {
    type: "submit",
    disabled: loading || !token.trim(),
    rightIcon: !loading && /*#__PURE__*/React.createElement(Icon, {
      name: "arrow-right",
      size: 16
    }),
    style: {
      width: "100%"
    }
  }, loading ? "Connecting…" : "Connect")), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 11,
      color: "hsl(var(--muted-foreground))",
      textAlign: "center",
      marginTop: 22,
      lineHeight: 1.5
    }
  }, "Token was generated during installation. Check the server terminal output or your .env file."), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 11,
      color: "hsl(var(--primary))",
      textAlign: "center",
      marginTop: 10,
      opacity: 0.8
    }
  }, "Demo \u2014 type anything and press Connect.")));
}
window.KitLogin = KitLogin;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/personal-agent/Login.jsx", error: String((e && e.message) || e) }); }

// ui_kits/personal-agent/RightPanel.jsx
try { (() => {
/* Right panel — tabbed. "Widgets" hosts the HMG Memory Graph + Tasks widgets. */
function KitRightPanel({
  open,
  onToggle
}) {
  const {
    WidgetCard,
    HmgGraph,
    HmgHexGrid,
    Badge
  } = window.PersonalAgentDesignSystem_94ad89;
  const {
    Icon
  } = window.PA;
  const [tab, setTab] = React.useState("widgets");
  const [view, setView] = React.useState("graph");
  const [biomes, setBiomes] = React.useState({
    A: true,
    B: true,
    C: true
  });
  const [edges, setEdges] = React.useState(true);
  const [worm, setWorm] = React.useState(true);
  const TABS = [{
    id: "widgets",
    label: "Widgets",
    icon: "layout-grid"
  }, {
    id: "canvas",
    label: "Canvas",
    icon: "file-code-2"
  }, {
    id: "stream",
    label: "Stream",
    icon: "terminal"
  }, {
    id: "creative",
    label: "Creative",
    icon: "sparkles"
  }];
  if (!open) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 4,
        width: 48,
        borderLeft: "1px solid hsl(var(--border))",
        background: "hsl(var(--surface-2))",
        padding: "12px 4px",
        flexShrink: 0
      }
    }, /*#__PURE__*/React.createElement("button", {
      onClick: onToggle,
      title: "Expand",
      style: iconStripBtn()
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "panel-right-close",
      size: 16,
      style: {
        transform: "rotate(180deg)"
      }
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        width: 24,
        borderTop: "1px solid hsl(var(--border))",
        margin: "4px 0"
      }
    }), TABS.map(t => /*#__PURE__*/React.createElement("button", {
      key: t.id,
      onClick: () => {
        setTab(t.id);
        onToggle();
      },
      title: t.label,
      style: iconStripBtn(tab === t.id)
    }, /*#__PURE__*/React.createElement(Icon, {
      name: t.icon,
      size: 16
    }))));
  }
  const biomeList = ["A", "B", "C"].filter(b => biomes[b]);
  const BIOME_COLOR = {
    A: "#2DD4BF",
    B: "#FF6B6B",
    C: "#8892B0"
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      width: 440,
      borderLeft: "1px solid hsl(var(--border))",
      background: "hsl(var(--background))",
      flexShrink: 0,
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      borderBottom: "1px solid hsl(var(--border))",
      background: "hsl(var(--surface-2))",
      flexShrink: 0
    }
  }, TABS.map(t => /*#__PURE__*/React.createElement("button", {
    key: t.id,
    onClick: () => setTab(t.id),
    style: {
      flex: 1,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      gap: 6,
      padding: "10px 0",
      fontSize: 12,
      fontWeight: 500,
      cursor: "pointer",
      background: "transparent",
      border: "none",
      borderBottom: `2px solid ${tab === t.id ? "hsl(var(--primary))" : "transparent"}`,
      color: tab === t.id ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))",
      transition: "color var(--dur-fast)"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: t.icon,
    size: 16
  }), /*#__PURE__*/React.createElement("span", null, t.label))), /*#__PURE__*/React.createElement("button", {
    onClick: onToggle,
    title: "Collapse",
    style: {
      height: 38,
      width: 38,
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      background: "transparent",
      border: "none",
      color: "hsl(var(--muted-foreground))",
      cursor: "pointer"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "panel-right-close",
    size: 16
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minHeight: 0,
      overflowY: "auto",
      padding: 12,
      display: "flex",
      flexDirection: "column",
      gap: 12
    }
  }, tab === "widgets" && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(WidgetCard, {
    title: "Memory Graph",
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "network",
      size: 16
    }),
    onFullscreen: () => {},
    toolbar: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        borderRadius: 7,
        border: "1px solid hsl(var(--border))",
        overflow: "hidden"
      }
    }, ["graph", "hex"].map(v => /*#__PURE__*/React.createElement("button", {
      key: v,
      onClick: () => setView(v),
      style: {
        padding: "2px 9px",
        fontSize: 10,
        fontWeight: 700,
        textTransform: "capitalize",
        cursor: "pointer",
        border: "none",
        background: view === v ? "hsl(var(--primary))" : "transparent",
        color: view === v ? "hsl(var(--primary-foreground))" : "hsl(var(--muted-foreground))"
      }
    }, v))), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 10,
        color: "hsl(var(--muted-foreground))",
        fontFamily: "var(--font-mono)"
      }
    }, "37n \xB7 9w \xB7 3s"), view === "graph" && ["A", "B", "C"].map(b => /*#__PURE__*/React.createElement("button", {
      key: b,
      onClick: () => setBiomes(p => ({
        ...p,
        [b]: !p[b]
      })),
      style: {
        padding: "2px 8px",
        borderRadius: 6,
        fontSize: 10,
        fontWeight: 700,
        cursor: "pointer",
        border: `1px solid ${biomes[b] ? BIOME_COLOR[b] : "hsl(var(--border))"}`,
        background: biomes[b] ? BIOME_COLOR[b] + "22" : "transparent",
        color: biomes[b] ? BIOME_COLOR[b] : "hsl(var(--muted-foreground))"
      }
    }, b)), view === "graph" && /*#__PURE__*/React.createElement("label", {
      style: {
        display: "flex",
        alignItems: "center",
        gap: 4,
        fontSize: 10,
        color: "hsl(var(--muted-foreground))",
        cursor: "pointer"
      }
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: edges,
      onChange: e => setEdges(e.target.checked),
      style: {
        width: 12,
        height: 12,
        accentColor: "#2DD4BF"
      }
    }), "edges"), view === "graph" && /*#__PURE__*/React.createElement("label", {
      style: {
        display: "flex",
        alignItems: "center",
        gap: 4,
        fontSize: 10,
        color: "hsl(var(--muted-foreground))",
        cursor: "pointer"
      }
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: worm,
      onChange: e => setWorm(e.target.checked),
      style: {
        width: 12,
        height: 12,
        accentColor: "#A78BFA"
      }
    }), "wormholes"))
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 8
    }
  }, view === "graph" ? /*#__PURE__*/React.createElement(HmgGraph, {
    height: 300,
    showEdges: edges,
    showWormholes: worm,
    showLabels: "hover",
    key: biomeList.join("")
  }) : /*#__PURE__*/React.createElement(HmgHexGrid, {
    height: 300
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexWrap: "wrap",
      gap: 12,
      padding: "8px 4px 2px",
      fontSize: 10,
      color: "hsl(var(--muted-foreground))"
    }
  }, view === "graph" ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Legend, {
    c: "#2DD4BF",
    t: "Positive"
  }), /*#__PURE__*/React.createElement(Legend, {
    c: "#FF6B6B",
    t: "Negative"
  }), /*#__PURE__*/React.createElement(Legend, {
    c: "#8892B0",
    t: "Neutral"
  }), /*#__PURE__*/React.createElement(Legend, {
    c: "#22D3EE",
    t: "macro"
  }), /*#__PURE__*/React.createElement(Legend, {
    c: "#F59E0B",
    t: "event"
  }), /*#__PURE__*/React.createElement(Legend, {
    c: "#A78BFA",
    t: "wormhole"
  })) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Legend, {
    c: "#8892B0",
    t: "micro"
  }), /*#__PURE__*/React.createElement(Legend, {
    c: "#E0A83A",
    t: "\u25C6 macro"
  }), /*#__PURE__*/React.createElement(Legend, {
    c: "#43C463",
    t: "active"
  }), /*#__PURE__*/React.createElement("span", null, "hover a macro \xB7 click to compress"))))), /*#__PURE__*/React.createElement(WidgetCard, {
    title: "Tasks",
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "list-todo",
      size: 16
    }),
    toolbar: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Badge, {
      variant: "outline",
      uppercase: true,
      tone: "neutral"
    }, "Autonomy"), /*#__PURE__*/React.createElement(Badge, {
      variant: "outline",
      uppercase: true,
      tone: "emerald"
    }, "Background"))
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 12
    }
  }, /*#__PURE__*/React.createElement(TaskStep, {
    done: true,
    text: "Pull hex-graph endpoint"
  }), /*#__PURE__*/React.createElement(TaskStep, {
    done: true,
    text: "Assign emotional coordinates"
  }), /*#__PURE__*/React.createElement(TaskStep, {
    text: "Cluster wormhole bridges"
  }), /*#__PURE__*/React.createElement(TaskStep, {
    text: "Nightly dream consolidation"
  })))), tab !== "widgets" && /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 12,
      height: "100%",
      color: "hsl(var(--muted-foreground))",
      textAlign: "center",
      padding: 24
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      height: 56,
      width: 56,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: "var(--radius-2xl)",
      background: "hsl(var(--surface-2))",
      border: "1px solid hsl(var(--border))"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: TABS.find(t => t.id === tab).icon,
    size: 26,
    color: "hsl(var(--primary) / 0.6)"
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      fontSize: 14,
      fontWeight: 600,
      color: "hsl(var(--foreground))"
    }
  }, TABS.find(t => t.id === tab).label), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: "4px 0 0",
      fontSize: 12,
      maxWidth: 220
    }
  }, "This surface streams live as the agent works.")))));
}
function Legend({
  c,
  t
}) {
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 5
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 10,
      height: 10,
      borderRadius: 3,
      background: c
    }
  }), t);
}
function TaskStep({
  done,
  text
}) {
  const {
    Icon
  } = window.PA;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "flex-start",
      gap: 8,
      padding: "3px 0"
    }
  }, done ? /*#__PURE__*/React.createElement(Icon, {
    name: "check-circle-2",
    size: 13,
    color: "var(--status-done)",
    style: {
      marginTop: 1
    }
  }) : /*#__PURE__*/React.createElement("span", {
    style: {
      width: 12,
      height: 12,
      borderRadius: 999,
      border: "1px solid hsl(var(--border))",
      flexShrink: 0,
      marginTop: 1
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      lineHeight: 1.4,
      color: done ? "hsl(var(--muted-foreground))" : "hsl(var(--foreground))",
      textDecoration: done ? "line-through" : "none"
    }
  }, text));
}
function iconStripBtn(active) {
  return {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    height: 32,
    width: 32,
    borderRadius: "var(--radius-md)",
    border: "none",
    cursor: "pointer",
    background: active ? "hsl(var(--primary) / 0.1)" : "transparent",
    color: active ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))"
  };
}
window.KitRightPanel = KitRightPanel;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/personal-agent/RightPanel.jsx", error: String((e && e.message) || e) }); }

// ui_kits/personal-agent/Sidebar.jsx
try { (() => {
/* Left Sessions panel — SessionRow list, provider picker, search, new session. */
function KitSidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
  provider,
  onProvider,
  open,
  onToggle
}) {
  const {
    SessionRow,
    ProviderSelect,
    IconButton,
    Input
  } = window.PersonalAgentDesignSystem_94ad89;
  const {
    Icon
  } = window.PA;
  const [q, setQ] = React.useState("");
  const PROVIDERS = [{
    id: "codex",
    label: "Codex",
    free: true
  }, {
    id: "openclaw",
    label: "OpenClaw"
  }, {
    id: "claude_code",
    label: "Claude CLI",
    free: true
  }, {
    id: "anthropic",
    label: "Anthropic"
  }, {
    id: "openai",
    label: "OpenAI"
  }, {
    id: "ollama",
    label: "Ollama"
  }];
  if (!open) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
        width: 48,
        borderRight: "1px solid hsl(var(--border))",
        background: "hsl(var(--sidebar-background))",
        padding: "12px 0"
      }
    }, /*#__PURE__*/React.createElement(IconButton, {
      title: "Open sessions",
      onClick: onToggle
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "chevron-right"
    })), /*#__PURE__*/React.createElement(IconButton, {
      title: "New session",
      onClick: onNew
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "plus"
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 8,
        display: "flex",
        flexDirection: "column",
        gap: 4
      }
    }, sessions.slice(0, 5).map(s => /*#__PURE__*/React.createElement(IconButton, {
      key: s.id,
      active: s.id === activeId,
      title: s.title,
      onClick: () => onSelect(s.id)
    }, /*#__PURE__*/React.createElement(Icon, {
      name: s.status === "working" ? "loader" : s.status === "done" ? "check-circle" : "message-square",
      size: 14
    })))));
  }
  const filtered = sessions.filter(s => s.title.toLowerCase().includes(q.toLowerCase()));
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      width: 260,
      borderRight: "1px solid hsl(var(--border))",
      background: "hsl(var(--sidebar-background))",
      overflow: "hidden",
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      borderBottom: "1px solid hsl(var(--border))",
      padding: "10px 12px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "message-square",
    size: 16,
    color: "hsl(var(--primary))"
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 14,
      fontWeight: 600,
      color: "hsl(var(--foreground))"
    }
  }, "Sessions")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 2
    }
  }, /*#__PURE__*/React.createElement(IconButton, {
    size: "sm",
    title: "New session",
    onClick: onNew
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "plus"
  })), /*#__PURE__*/React.createElement(IconButton, {
    size: "sm",
    title: "Collapse",
    onClick: onToggle
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "chevron-left"
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "8px 12px"
    }
  }, /*#__PURE__*/React.createElement(Input, {
    surface: "flush",
    leftIcon: /*#__PURE__*/React.createElement(Icon, {
      name: "search",
      size: 14
    }),
    value: q,
    onChange: e => setQ(e.target.value),
    placeholder: "Search sessions...",
    style: {
      height: 34,
      fontSize: 12,
      paddingLeft: 34
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "0 12px 8px",
      borderBottom: "1px solid hsl(var(--border))"
    }
  }, /*#__PURE__*/React.createElement(ProviderSelect, {
    options: PROVIDERS,
    value: provider,
    onChange: onProvider,
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "cpu",
      size: 14
    })
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflowY: "auto",
      padding: "6px"
    }
  }, filtered.map(s => /*#__PURE__*/React.createElement(SessionRow, {
    key: s.id,
    active: s.id === activeId,
    pinned: s.pinned,
    title: s.title,
    meta: `${s.msgs} msgs · ${s.ago}`,
    status: s.status,
    onClick: () => onSelect(s.id)
  })), filtered.length === 0 && /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 12,
      color: "hsl(var(--muted-foreground))",
      textAlign: "center",
      padding: "24px 0"
    }
  }, "No sessions found")));
}
window.KitSidebar = KitSidebar;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/personal-agent/Sidebar.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.CanvasWidget = __ds_scope.CanvasWidget;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.DiffView = __ds_scope.DiffView;

__ds_ns.HmgGraph = __ds_scope.HmgGraph;

__ds_ns.HmgHexGrid = __ds_scope.HmgHexGrid;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.MessageBubble = __ds_scope.MessageBubble;

__ds_ns.Pill = __ds_scope.Pill;

__ds_ns.PlanTracker = __ds_scope.PlanTracker;

__ds_ns.ProviderSelect = __ds_scope.ProviderSelect;

__ds_ns.SessionRow = __ds_scope.SessionRow;

__ds_ns.ToolCallBlock = __ds_scope.ToolCallBlock;

__ds_ns.WidgetCard = __ds_scope.WidgetCard;

})();
