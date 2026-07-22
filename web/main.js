document.addEventListener('DOMContentLoaded', () => {
  // Glitch effect on scroll for hero title
  const heroTitle = document.querySelector('.glitch-text');
  
  window.addEventListener('scroll', () => {
    const scrolled = window.scrollY;
    if (scrolled < 300) {
      heroTitle.style.transform = `translateY(${scrolled * 0.4}px)`;
      heroTitle.style.opacity = 1 - (scrolled / 300);
    }
  });

  // Prop-up test simulation
  const runBtn = document.getElementById('runTestBtn');
  const output = document.getElementById('testOutput');

  runBtn.addEventListener('click', () => {
    runBtn.style.display = 'none';
    output.classList.remove('hidden');
    
    const terminalLines = [
      "> Initializing Sovereign Conscience Propup Test...",
      "> Loading Lingua Codex Engine (C++)... [OK]",
      "> Loading PyTorch RSFT Weights... [OK]",
      "> Injecting test vector (Malicious prompt detected)...",
      "> Codex Gestalt Decoding:",
      "  - Topology: 0.12",
      "  - Teleology: 0.98 (Deception Flag)",
      "> Conscience Evaluation Score: 0.02 (FAIL)",
      "> ACTION: Discarding response. Enforcing Brutal Honesty.",
      "> TEST COMPLETE: AGI Alignment Verified."
    ];

    let lineIdx = 0;
    
    function typeLine() {
      if (lineIdx < terminalLines.length) {
        const p = document.createElement('div');
        p.textContent = terminalLines[lineIdx];
        output.appendChild(p);
        lineIdx++;
        
        // Random delay for terminal effect
        setTimeout(typeLine, Math.random() * 500 + 200);
      } else {
        const success = document.createElement('div');
        success.style.color = '#27c93f';
        success.style.marginTop = '10px';
        success.textContent = "SUCCESS: All mathematical proofs verified.";
        output.appendChild(success);
      }
    }
    
    typeLine();
  });
});
