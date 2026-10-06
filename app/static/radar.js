// Radar graph (docs/specs/ui.md, Radar): cytoscape with fixed positions from views.radar_graph().
// Hover a node: its neighbourhood stays, the rest fades. Click a problem: open it.
(function () {
  const box = document.getElementById("radar-graph");
  if (!box || typeof cytoscape === "undefined") return;

  fetch(box.dataset.src).then((r) => r.json()).then((graph) => {
    const cy = cytoscape({
      container: box,
      elements: [...graph.nodes, ...graph.edges],
      layout: { name: "preset", fit: false, padding: 0 },
      userZoomingEnabled: false, userPanningEnabled: false, boxSelectionEnabled: false, autoungrabify: true,
      style: [
        { selector: "node", style: {
          "font-family": "system-ui, -apple-system, Segoe UI, Roboto, sans-serif", "font-size": 12,
          color: "#2f3941", "text-valign": "center", "min-zoomed-font-size": 6, "transition-property": "opacity",
          "transition-duration": "120ms" } },
        { selector: "node.area", style: {
          shape: "round-rectangle", width: 96, height: 26, "background-color": "#ffffff", "border-width": 1,
          "border-color": "#aeb8bd", label: "data(label)", "font-weight": 600, color: "#17202a" } },
        { selector: "node.problem", style: {
          width: "data(size)", height: "data(size)", "background-color": "data(color)", label: "data(label)",
          "text-halign": "right", "text-margin-x": 8, "text-wrap": "ellipsis", "text-max-width": 300,
          "text-background-color": "#ffffff", "text-background-opacity": 0.9, "text-background-padding": 2 } },
        { selector: "node.customer", style: {
          width: 10, height: 10, "background-color": "#8aa6b5", label: "data(label)", "text-halign": "right",
          "text-margin-x": 6, "font-size": 11, color: "#5c6970",
          "text-background-color": "#ffffff", "text-background-opacity": 0.9, "text-background-padding": 1 } },
        { selector: "node.customer.multi", style: {
          width: 12, height: 12, "background-color": "#ffffff", "border-width": 2.5, "border-color": "#b8243a",
          color: "#b8243a", "font-weight": 600 } },
        { selector: "edge", style: {
          width: "data(width)", "line-color": "#d8dcde", "curve-style": "bezier", opacity: 0.9,
          "transition-property": "opacity, line-color", "transition-duration": "120ms" } },
        { selector: ".faded", style: { opacity: 0.12 } },
        { selector: "edge.hot", style: { "line-color": "#5c6970", opacity: 1 } },
      ],
    });

    const focus = (node) => {
      let hood;
      if (node.data("kind") === "customer") {  // the customer's problems and their areas, not the other customers
        const toAreas = node.neighborhood("node.problem").connectedEdges().filter((e) => e.source().hasClass("area"));
        hood = node.closedNeighborhood().union(toAreas).union(toAreas.sources());
      } else {  // a problem brings its area and customers; an area brings its problems and their customers
        const problems = node.data("kind") === "problem" ? node : node.neighborhood("node.problem");
        hood = node.closedNeighborhood().union(problems.closedNeighborhood());
      }
      cy.elements().addClass("faded").removeClass("hot");
      hood.removeClass("faded");
      hood.edges().addClass("hot");
    };
    cy.on("mouseover", "node", (e) => focus(e.target));
    cy.on("mouseout", "node", () => cy.elements().removeClass("faded hot"));
    cy.on("tap", "node.problem", (e) => { window.location.href = e.target.data("href"); });
    cy.on("mouseover", "node.problem", () => { box.style.cursor = "pointer"; });
    cy.on("mouseout", "node.problem", () => { box.style.cursor = "default"; });
  });
})();
