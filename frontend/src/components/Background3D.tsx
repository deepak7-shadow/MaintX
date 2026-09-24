import { useEffect, useRef } from 'react';
import * as THREE from 'three';

interface Background3DProps {
  scrollTargetRef?: React.RefObject<HTMLElement | null>;
}

export function Background3D({ scrollTargetRef }: Background3DProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // ── 1. Renderer Setup ────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      powerPreference: 'high-performance',
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);

    // ── 2. Scene & Camera Setup ──────────────────────────────────────────────
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x060913, 0.006);

    const camera = new THREE.PerspectiveCamera(
      52,
      window.innerWidth / window.innerHeight,
      0.1,
      1000
    );
    camera.position.set(0, 4, 68);

    // ── 3. Lighting ──────────────────────────────────────────────────────────
    const ambientLight = new THREE.AmbientLight(0x1a4060, 3.5);
    scene.add(ambientLight);

    const cyanLight = new THREE.PointLight(0x00f0ff, 8, 200);
    cyanLight.position.set(25, 20, 30);
    scene.add(cyanLight);

    const emeraldLight = new THREE.PointLight(0x10b981, 6, 180);
    emeraldLight.position.set(-25, -15, 20);
    scene.add(emeraldLight);

    const purpleLight = new THREE.PointLight(0x818cf8, 5, 160);
    purpleLight.position.set(0, 35, -20);
    scene.add(purpleLight);

    const whiteBooster = new THREE.DirectionalLight(0xffffff, 1.2);
    whiteBooster.position.set(0, 10, 50);
    scene.add(whiteBooster);

    // ── 4. Infinite Cybernetic Grid Floor (OT Space) ─────────────────────────
    const gridHelper = new THREE.GridHelper(260, 52, 0x00f0ff, 0x052e3d);
    gridHelper.position.set(0, -28, -20);
    const gridMat = gridHelper.material as THREE.LineBasicMaterial;
    gridMat.transparent = true;
    gridMat.opacity = 0.55;
    gridMat.blending = THREE.AdditiveBlending;
    scene.add(gridHelper);

    // Second elevated digital ceiling grid
    const ceilingGrid = new THREE.GridHelper(260, 52, 0x0e7490, 0x041f29);
    ceilingGrid.position.set(0, 38, -20);
    const ceilMat = ceilingGrid.material as THREE.LineBasicMaterial;
    ceilMat.transparent = true;
    ceilMat.opacity = 0.30;
    ceilMat.blending = THREE.AdditiveBlending;
    scene.add(ceilingGrid);

    // ── 5. Cryptographic Gyroscope (Zero-Trust Security Core) ─────────────────
    const gyroGroup = new THREE.Group();
    gyroGroup.position.set(20, 8, -5);

    const createRing = (
      radius: number,
      tube: number,
      segs: number,
      color: number,
      opacity: number,
      rotX = 0,
      rotY = 0
    ) => {
      const geo = new THREE.TorusGeometry(radius, tube, 14, segs);
      const mat = new THREE.MeshBasicMaterial({
        color,
        wireframe: true,
        transparent: true,
        opacity,
        blending: THREE.AdditiveBlending,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.rotation.x = rotX;
      mesh.rotation.y = rotY;
      gyroGroup.add(mesh);
      return mesh;
    };

    const ringOuter = createRing(32, 0.38, 80, 0x00f0ff, 0.75);
    const ringMid   = createRing(24, 0.30, 64, 0x10b981, 0.65, Math.PI / 3, Math.PI / 6);
    const ringInner = createRing(16, 0.24, 48, 0x38bdf8, 0.60, -Math.PI / 4, Math.PI / 3);

    // Central Core Octahedron / Security Node
    const coreGeo = new THREE.OctahedronGeometry(6.5, 1);
    const coreMat = new THREE.MeshBasicMaterial({
      color: 0x06b6d4,
      wireframe: true,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
    });
    const coreMesh = new THREE.Mesh(coreGeo, coreMat);
    gyroGroup.add(coreMesh);

    scene.add(gyroGroup);

    // ── 6. Floating 3D Cryptographic Ledger Blocks & Chain Linkage ────────────
    const blockGroup = new THREE.Group();
    const numBlocks = 14;
    const blockMeshes: THREE.Mesh[] = [];
    const blockPositions: THREE.Vector3[] = [];

    const colors = [0x00f0ff, 0x10b981, 0x38bdf8, 0x818cf8, 0xf59e0b];

    for (let i = 0; i < numBlocks; i++) {
      const size = 3.6 + (i % 3) * 0.6;
      const bGeo = new THREE.BoxGeometry(size, size, size);

      const color = colors[i % colors.length];
      const bMat = new THREE.MeshBasicMaterial({
        color,
        wireframe: true,
        transparent: true,
        opacity: 0.55,
        blending: THREE.AdditiveBlending,
      });

      const bMesh = new THREE.Mesh(bGeo, bMat);

      // Distribute in a winding S-corridor through depth
      const side = (i % 2 === 0 ? 1 : -1);
      const x = side * (20 + (i % 4) * 8) + Math.sin(i * 0.8) * 6;
      const y = -14 + (i * 3.5) - (i > 7 ? 20 : 0);
      const z = 30 - i * 14;

      bMesh.position.set(x, y, z);
      bMesh.rotation.set(Math.sin(i), Math.cos(i), i * 0.4);

      blockMeshes.push(bMesh);
      blockPositions.push(new THREE.Vector3(x, y, z));
      blockGroup.add(bMesh);
    }

    // Connect blocks with cryptographic laser chain line
    const chainGeo = new THREE.BufferGeometry().setFromPoints(blockPositions);
    const chainMat = new THREE.LineBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.40,
      blending: THREE.AdditiveBlending,
    });
    const chainLine = new THREE.Line(chainGeo, chainMat);
    blockGroup.add(chainLine);

    scene.add(blockGroup);

    // ── 7. Luminous Cyber Particle Nebula (Data Streams) ──────────────────────
    const pCanvas = document.createElement('canvas');
    pCanvas.width = pCanvas.height = 32;
    const pCtx = pCanvas.getContext('2d');
    if (pCtx) {
      const grad = pCtx.createRadialGradient(16, 16, 0, 16, 16, 16);
      grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
      grad.addColorStop(0.25, 'rgba(56, 189, 248, 0.95)');
      grad.addColorStop(0.65, 'rgba(14, 165, 233, 0.35)');
      grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
      pCtx.fillStyle = grad;
      pCtx.fillRect(0, 0, 32, 32);
    }
    const particleTexture = new THREE.CanvasTexture(pCanvas);

    const particleCount = 1800;
    const pPositions = new Float32Array(particleCount * 3);
    const pColors = new Float32Array(particleCount * 3);
    const pVelocities = new Float32Array(particleCount * 3);

    const colCyan = new THREE.Color(0x00f0ff);
    const colEmerald = new THREE.Color(0x10b981);
    const colAmber = new THREE.Color(0xf59e0b);
    const colSky = new THREE.Color(0x38bdf8);

    for (let i = 0; i < particleCount; i++) {
      pPositions[i * 3]     = (Math.random() - 0.5) * 220;
      pPositions[i * 3 + 1] = (Math.random() - 0.5) * 180;
      pPositions[i * 3 + 2] = (Math.random() - 0.5) * 160;

      pVelocities[i * 3]     = (Math.random() - 0.5) * 0.06;
      pVelocities[i * 3 + 1] = Math.random() * 0.12 + 0.03;
      pVelocities[i * 3 + 2] = (Math.random() - 0.5) * 0.06;

      const rand = Math.random();
      const c = rand < 0.55 ? colCyan : rand < 0.8 ? colSky : rand < 0.93 ? colEmerald : colAmber;
      pColors[i * 3]     = c.r;
      pColors[i * 3 + 1] = c.g;
      pColors[i * 3 + 2] = c.b;
    }

    const particlesGeo = new THREE.BufferGeometry();
    particlesGeo.setAttribute('position', new THREE.BufferAttribute(pPositions, 3));
    particlesGeo.setAttribute('color', new THREE.BufferAttribute(pColors, 3));

    const particlesMat = new THREE.PointsMaterial({
      size: 3.2,
      map: particleTexture,
      vertexColors: true,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const particles = new THREE.Points(particlesGeo, particlesMat);
    scene.add(particles);

    // ── 8. Interactive Mouse & Scroll State ────────────────────────────────────
    const mouse = { x: 0, y: 0, targetX: 0, targetY: 0 };
    const scroll = { current: 0, target: 0 };

    const onMouseMove = (e: MouseEvent) => {
      mouse.targetX = (e.clientX / window.innerWidth - 0.5) * 2;
      mouse.targetY = (e.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener('mousemove', onMouseMove);

    const updateScrollProgress = () => {
      let ratio = 0;
      const targetEl = scrollTargetRef?.current;
      if (targetEl) {
        const max = targetEl.scrollHeight - targetEl.clientHeight;
        if (max > 0) {
          ratio = targetEl.scrollTop / max;
        }
      } else {
        const max = document.documentElement.scrollHeight - window.innerHeight;
        if (max > 0) {
          ratio = window.scrollY / max;
        }
      }
      scroll.target = Math.max(0, Math.min(1, ratio));
    };

    const targetEl = scrollTargetRef?.current;
    if (targetEl) {
      targetEl.addEventListener('scroll', updateScrollProgress, { passive: true });
    }
    window.addEventListener('scroll', updateScrollProgress, { passive: true });

    const onResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
      updateScrollProgress();
    };
    window.addEventListener('resize', onResize);

    // Initial compute
    updateScrollProgress();

    // ── 9. Render & Animation Loop ───────────────────────────────────────────
    let animId: number;
    let clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);

      clock.getDelta();
      const elapsedTime = clock.getElapsedTime();

      // Smooth lerp mouse coordinates
      mouse.x += (mouse.targetX - mouse.x) * 0.05;
      mouse.y += (mouse.targetY - mouse.y) * 0.05;

      // Smooth lerp scroll progress (spring dampening)
      scroll.current += (scroll.target - scroll.current) * 0.065;
      const s = scroll.current;

      // ── 3D Camera Flight through Cyber Space
      camera.position.z = 68 - s * 52;
      camera.position.y = 4 - s * 22 - mouse.y * 5;
      camera.position.x = mouse.x * 7 + Math.sin(s * Math.PI) * 9;

      camera.rotation.x = -mouse.y * 0.06 + s * 0.14;
      camera.rotation.y = -mouse.x * 0.06 + (s - 0.5) * 0.16;
      camera.rotation.z = Math.sin(s * 2.5) * 0.025;

      // ── Rotate Gyroscope Rings
      ringOuter.rotation.y += 0.0035;
      ringOuter.rotation.x += 0.002;
      ringMid.rotation.x += 0.004;
      ringMid.rotation.z -= 0.0025;
      ringInner.rotation.y -= 0.005;
      ringInner.rotation.x += 0.003;
      coreMesh.rotation.x += 0.006;
      coreMesh.rotation.y += 0.008;

      gyroGroup.position.y = 8 - s * 26;
      gyroGroup.position.z = -5 - s * 16;
      gyroGroup.rotation.z = s * 0.7;

      // ── Animate 3D Ledger Blocks
      blockMeshes.forEach((mesh, idx) => {
        mesh.rotation.x += 0.004 * (idx % 2 === 0 ? 1 : -1);
        mesh.rotation.y += 0.006 * (idx % 3 === 0 ? -1 : 1);
        mesh.rotation.z += 0.002;
      });

      // ── Pulse Lights with Cyber Rhythm
      cyanLight.intensity = 7.5 + Math.sin(elapsedTime * 2.2) * 2.0;
      emeraldLight.intensity = 5.5 + Math.cos(elapsedTime * 1.8) * 1.5;

      // ── Infinite Ground Grid Motion
      gridHelper.position.z = -20 + (s * 40 + elapsedTime * 1.5) % 10;
      ceilingGrid.position.z = -20 + (s * 35 + elapsedTime * 1.2) % 10;

      // ── Drift Cyber Sparks
      const pArr = particlesGeo.attributes.position.array as Float32Array;
      for (let i = 0, len = particleCount; i < len; i++) {
        pArr[i * 3 + 1] += pVelocities[i * 3 + 1];
        pArr[i * 3]     += pVelocities[i * 3] + mouse.x * 0.025;
        pArr[i * 3 + 2] += pVelocities[i * 3 + 2];

        // Wrap around volume
        if (pArr[i * 3 + 1] > 90) {
          pArr[i * 3 + 1] = -90;
          pArr[i * 3]     = (Math.random() - 0.5) * 220;
          pArr[i * 3 + 2] = (Math.random() - 0.5) * 160;
        }
      }
      particlesGeo.attributes.position.needsUpdate = true;

      renderer.render(scene, camera);
    };

    animate();

    // ── 10. Cleanup on unmount ───────────────────────────────────────────────
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('resize', onResize);
      window.removeEventListener('scroll', updateScrollProgress);
      if (targetEl) {
        targetEl.removeEventListener('scroll', updateScrollProgress);
      }

      particlesGeo.dispose();
      particlesMat.dispose();
      particleTexture.dispose();
      gridHelper.dispose();
      ceilingGrid.dispose();
      renderer.dispose();
    };
  }, [scrollTargetRef]);

  return (
    <div
      aria-hidden="true"
      className="fixed inset-0 pointer-events-none select-none z-0 overflow-hidden"
    >
      {/* 3D WebGL Canvas */}
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full block" />

      {/* Radial Vignette & Atmospheric Depth Mask (Ensures ultra-clean contrast for tables, charts, & typography) */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse at 50% 40%, rgba(6, 9, 19, 0.08) 0%, rgba(6, 9, 19, 0.25) 55%, rgba(6, 9, 19, 0.55) 85%, rgba(6, 9, 19, 0.80) 100%)',
        }}
      />

      {/* Cybernetic Horizontal Scanline / Grid overlay */}
      <div
        className="absolute inset-0 opacity-[0.06]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(56, 189, 248, 0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(56, 189, 248, 0.6) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      {/* Subtle Top & Bottom Cinematic Edge Gradients */}
      <div className="absolute top-0 left-0 right-0 h-16 bg-gradient-to-b from-[#060913]/60 to-transparent" />
      <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-[#060913]/60 to-transparent" />
    </div>
  );
}
