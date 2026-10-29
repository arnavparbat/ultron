import * as THREE from "three";

export class UltronSphere {
  constructor(container) {
    this.container = container;
    this.state = "idle"; // idle | listening | processing | complete
    this.width = container.clientWidth || 320;
    this.height = container.clientHeight || 320;

    // Target visual properties for smooth interpolation
    this.targetScale = 1.0;
    this.currentScale = 1.0;
    this.targetColor = new THREE.Color(0x00f0ff); // Cool cyan
    this.currentColor = new THREE.Color(0x00f0ff);
    this.targetSecondaryColor = new THREE.Color(0x00ff88); // Neon green
    this.currentSecondaryColor = new THREE.Color(0x00ff88);
    this.rotationSpeed = 0.015;
    this.targetRotationSpeed = 0.015;

    this.initScene();
    this.createObjects();
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  initScene() {
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(45, this.width / this.height, 0.1, 1000);
    this.camera.position.z = 4.8;

    this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    this.renderer.setSize(this.width, this.height);
    this.renderer.setPixelRatio(window.devicePixelRatio || 1);
    this.container.appendChild(this.renderer.domElement);

    this.clock = new THREE.Clock();

    window.addEventListener("resize", () => {
      if (!this.container) return;
      this.width = this.container.clientWidth;
      this.height = this.container.clientHeight;
      this.camera.aspect = this.width / this.height;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(this.width, this.height);
    });
  }

  createObjects() {
    this.sphereGroup = new THREE.Group();
    this.scene.add(this.sphereGroup);

    // 1. Outer Icosahedron Wireframe Sphere
    const icoGeo = new THREE.IcosahedronGeometry(1.4, 2);
    const wireGeo = new THREE.WireframeGeometry(icoGeo);
    this.lineMat = new THREE.LineBasicMaterial({
      color: this.currentColor,
      transparent: true,
      opacity: 0.85,
      linewidth: 2
    });
    this.wireMesh = new THREE.LineSegments(wireGeo, this.lineMat);
    this.sphereGroup.add(this.wireMesh);

    // 2. Vertex Nodes (glowing junction points)
    const pointsMat = new THREE.PointsMaterial({
      color: this.currentSecondaryColor,
      size: 0.055,
      transparent: true,
      opacity: 0.9
    });
    this.pointsMesh = new THREE.Points(icoGeo, pointsMat);
    this.sphereGroup.add(this.pointsMesh);

    // 3. Orbital Wireframe Rings that wrap around the sphere
    this.rings = [];
    const ringRadii = [1.45, 1.48, 1.51];
    ringRadii.forEach((radius, i) => {
      const ringGeo = new THREE.BufferGeometry();
      const segments = 64;
      const positions = [];
      for (let j = 0; j <= segments; j++) {
        const theta = (j / segments) * Math.PI * 2;
        positions.push(Math.cos(theta) * radius, Math.sin(theta) * radius, 0);
      }
      ringGeo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      const ringMat = new THREE.LineBasicMaterial({
        color: i % 2 === 0 ? this.currentColor : this.currentSecondaryColor,
        transparent: true,
        opacity: 0.6,
        linewidth: 1.5
      });
      const ring = new THREE.Line(ringGeo, ringMat);
      ring.rotation.x = (Math.PI / 4) * (i + 1);
      ring.rotation.y = (Math.PI / 3) * (i + 1);
      this.sphereGroup.add(ring);
      this.rings.push(ring);
    });

    // 4. Inner Pulsing Core
    const innerGeo = new THREE.IcosahedronGeometry(0.65, 1);
    const innerWire = new THREE.WireframeGeometry(innerGeo);
    this.innerMat = new THREE.LineBasicMaterial({
      color: this.currentSecondaryColor,
      transparent: true,
      opacity: 0.75
    });
    this.innerMesh = new THREE.LineSegments(innerWire, this.innerMat);
    this.sphereGroup.add(this.innerMesh);
  }

  setState(newState) {
    if (this.state === newState) return;
    this.state = newState;

    switch (newState) {
      case "idle":
        this.targetScale = 1.0;
        this.targetColor.set(0x00f0ff); // Cool Cyan
        this.targetSecondaryColor.set(0x00ff88); // Neon Green
        this.targetRotationSpeed = 0.012;
        break;

      case "listening":
        this.targetScale = 1.32; // Scale up noticeably
        this.targetColor.set(0xffaa00); // Gold / Amber
        this.targetSecondaryColor.set(0xffd700); // Bright Amber
        this.targetRotationSpeed = 0.005; // Attentive, slower rotation
        break;

      case "processing":
        this.targetScale = 1.32;
        this.targetColor.set(0xff8800); // Intense vibrating Amber
        this.targetSecondaryColor.set(0xffcc00);
        this.targetRotationSpeed = 0.025;
        break;

      case "complete":
        this.targetScale = 1.05;
        this.targetColor.set(0x00ffcc); // Return toward Cyan
        this.targetSecondaryColor.set(0x00ff66);
        this.targetRotationSpeed = 0.015;
        break;
    }
  }

  animate() {
    requestAnimationFrame(this.animate);
    const delta = this.clock.getDelta();
    const elapsedTime = this.clock.getElapsedTime();

    // 1. Smoothly interpolate scale and colors (200-300ms easing)
    const lerpFactor = Math.min(delta * 6.0, 1.0);
    this.currentScale += (this.targetScale - this.currentScale) * lerpFactor;
    this.currentColor.lerp(this.targetColor, lerpFactor);
    this.currentSecondaryColor.lerp(this.targetSecondaryColor, lerpFactor);
    this.rotationSpeed += (this.targetRotationSpeed - this.rotationSpeed) * lerpFactor;

    // Apply colors to materials
    this.lineMat.color.copy(this.currentColor);
    this.pointsMesh.material.color.copy(this.currentSecondaryColor);
    this.innerMat.color.copy(this.currentSecondaryColor);
    this.rings.forEach((r, idx) => {
      r.material.color.copy(idx % 2 === 0 ? this.currentColor : this.currentSecondaryColor);
    });

    // 2. Continuous rotation
    this.sphereGroup.rotation.y += this.rotationSpeed;
    this.sphereGroup.rotation.x += this.rotationSpeed * 0.45;

    // Counter-rotate rings for multi-dimensional sphere contour
    this.rings.forEach((ring, idx) => {
      ring.rotation.z += (idx + 1) * 0.008;
      ring.rotation.x += 0.006;
    });

    // Inner core breathing / pulsing
    const breathe = Math.sin(elapsedTime * 2.5) * 0.08;
    this.innerMesh.scale.set(1 + breathe, 1 + breathe, 1 + breathe);
    this.innerMesh.rotation.y -= 0.02;

    // 3. Processing State Vibration / Jitter
    let jitterX = 0;
    let jitterY = 0;
    let jitterZ = 0;

    if (this.state === "processing") {
      const shakeFreq = 48.0;
      const shakeAmp = 0.045;
      jitterX = (Math.random() - 0.5) * shakeAmp;
      jitterY = Math.sin(elapsedTime * shakeFreq) * (shakeAmp * 0.8);
      jitterZ = Math.cos(elapsedTime * shakeFreq) * (shakeAmp * 0.8);
    }

    this.sphereGroup.position.set(jitterX, jitterY, jitterZ);
    this.sphereGroup.scale.set(this.currentScale, this.currentScale, this.currentScale);

    this.renderer.render(this.scene, this.camera);
  }
}
