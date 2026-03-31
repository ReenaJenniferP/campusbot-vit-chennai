const canvas = document.getElementById("bgCanvas");

if (canvas) {
  const ctx = canvas.getContext("2d");

  let nodes = [];
  const NODE_COUNT = 45;
  const MAX_DISTANCE = 140;

  function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  function createNodes() {
    nodes = [];
    for (let i = 0; i < NODE_COUNT; i++) {
      nodes.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        radius: Math.random() * 2 + 1.5,
        dx: (Math.random() - 0.5) * 0.6,
        dy: (Math.random() - 0.5) * 0.6
      });
    }
  }

  function drawNode(node) {
    ctx.beginPath();
    ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(185,168,255,0.55)";
    ctx.fill();
  }

  function drawLine(a, b, distance) {
    const opacity = 1 - distance / MAX_DISTANCE;

    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.strokeStyle = `rgba(122,166,255,${opacity * 0.18})`;
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  function updateNodes() {
    for (const node of nodes) {
      node.x += node.dx;
      node.y += node.dy;

      if (node.x <= 0 || node.x >= canvas.width) {
        node.dx *= -1;
      }
      if (node.y <= 0 || node.y >= canvas.height) {
        node.dy *= -1;
      }
    }
  }

  function connectNodes() {
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance < MAX_DISTANCE) {
          drawLine(nodes[i], nodes[j], distance);
        }
      }
    }
  }

  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    updateNodes();
    connectNodes();

    for (const node of nodes) {
      drawNode(node);
    }

    requestAnimationFrame(animate);
  }

  resizeCanvas();
  createNodes();
  animate();

  window.addEventListener("resize", () => {
    resizeCanvas();
    createNodes();
  });
}