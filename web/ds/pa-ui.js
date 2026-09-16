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
    return String(name).replace(/(^|-)([a-z])/g, function (_, __, c) { return c.toUpperCase(); });
  }
  // Recursively render an IconNode [tag, attrs, children] → React element.
  function renderNode(node, key) {
    if (!Array.isArray(node)) return null;
    var tag = node[0], attrs = node[1] || {}, children = node[2];
    if (typeof tag !== "string") return null;
    var kids = Array.isArray(children) ? children.map(function (c, i) { return renderNode(c, i); }) : null;
    return R.createElement(tag, Object.assign({ key: key }, attrs), kids);
  }
  function Icon(props) {
    props = props || {};
    var name = props.name, size = props.size || 16, stroke = props.stroke || 2;
    var color = props.color || "currentColor", style = props.style, className = props.className;
    var lib = window.lucide || {};
    var data = lib[name] || lib[toPascal(name)] || (lib.icons && (lib.icons[name] || lib.icons[toPascal(name)]));
    if (!data || !R || !Array.isArray(data)) return null;

    // Determine the list of shape child-nodes to draw inside our <svg>.
    var shapes;
    if (typeof data[0] === "string") {
      // single IconNode
      if (data[0] === "svg") shapes = Array.isArray(data[2]) ? data[2] : [];
      else shapes = [data]; // a lone shape like ["path", {...}]
    } else {
      shapes = data; // already a list of shape nodes
    }

    var children = shapes.map(function (n, i) { return renderNode(n, i); }).filter(Boolean);
    return R.createElement(
      "svg",
      {
        width: size, height: size, viewBox: "0 0 24 24", fill: "none",
        stroke: color, strokeWidth: stroke, strokeLinecap: "round", strokeLinejoin: "round",
        className: className,
        style: Object.assign({ display: "inline-block", flexShrink: 0 }, style),
      },
      children
    );
  }
  window.PA = window.PA || {};
  window.PA.Icon = Icon;
})();
