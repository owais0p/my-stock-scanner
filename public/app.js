const scanBtn = document.getElementById('scan-btn');
const btnText = document.getElementById('btn-text');
const loadingSpinner = document.getElementById('loading-spinner');
const signalsContainer = document.getElementById('signals-container');
const scanStatus = document.getElementById('scan-status');
const emptyState = document.getElementById('empty-state');

async function triggerScan() {
    // UI State: Loading
    scanBtn.disabled = true;
    btnText.textContent = 'Scanning Market...';
    loadingSpinner.classList.remove('hidden');
    scanStatus.textContent = 'ACTIVE';
    scanStatus.classList.add('animate-pulse');

    try {
        const response = await fetch('/api/scan');
        const result = await response.json();

        if (result.status === 'success') {
            renderSignals(result.data);
            scanStatus.textContent = 'COMPLETE';
        } else {
            throw new Error('Scan failed');
        }
    } catch (error) {
        console.error('Scan Error:', error);
        scanStatus.textContent = 'ERROR';
        alert('Scanner connection failed. Please try again.');
    } finally {
        // UI State: Idle
        scanBtn.disabled = false;
        btnText.textContent = 'Re-Execute System Scan';
        loadingSpinner.classList.add('hidden');
        scanStatus.classList.remove('animate-pulse');
    }
}

function renderSignals(stocks) {
    if (stocks.length === 0) {
        emptyState.classList.remove('hidden');
        signalsContainer.innerHTML = '';
        signalsContainer.appendChild(emptyState);
        return;
    }

    emptyState.classList.add('hidden');
    signalsContainer.innerHTML = '';

    stocks.forEach((stock, index) => {
        const card = document.createElement('div');
        card.className = 'glass p-6 rounded-[2rem] card-anim relative overflow-hidden group';
        card.style.animationDelay = `${index * 0.1}s`;

        card.innerHTML = `
            <div class="absolute top-0 right-0 w-24 h-24 bg-accent/5 blur-2xl rounded-full -translate-y-1/2 translate-x-1/2"></div>
            
            <div class="flex justify-between items-start mb-6 relative z-10">
                <div>
                    <h3 class="font-extrabold text-2xl tracking-tighter leading-none mb-1 uppercase">${stock.ticker}</h3>
                    <div class="flex items-center gap-2">
                        <span class="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Setup</span>
                        <span class="text-[9px] font-extrabold text-accent uppercase tracking-widest">${stock.setup}</span>
                    </div>
                </div>
                <div class="bg-accent/10 px-3 py-1 rounded-full border border-accent/20">
                    <span class="text-[10px] font-black text-accent uppercase tracking-widest">Score: ${stock.score}</span>
                </div>
            </div>

            <div class="flex items-end justify-between relative z-10">
                <div>
                    <div class="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-1">Entry Price</div>
                    <div class="font-mono font-bold text-2xl">₹${stock.price.toLocaleString('en-IN')}</div>
                </div>
                <div class="text-right">
                    <div class="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-1">Pole Gain</div>
                    <div class="text-accent font-mono font-black text-xl">+${stock.pole_gain}%</div>
                </div>
            </div>

            <div class="mt-6 pt-4 border-t border-slate-500/10 flex justify-between items-center text-[9px] font-bold uppercase tracking-[0.2em] text-slate-600">
                <span>VCP Range: ${stock.vcp_range}%</span>
                <span>Length: ${stock.vcp_len}D</span>
            </div>
        `;

        signalsContainer.appendChild(card);
    });
}

scanBtn.addEventListener('click', triggerScan);
