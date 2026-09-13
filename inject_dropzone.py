import re
with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()
dropzone_html = """
<div id=\"apiConfigZone\" style=\"margin: 2rem auto 0; max-width: 600px; padding: 1rem; background: #f0f4f8; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);\">
    <label for=\"apiUrlInput\" style=\"display:block; font-size: 0.9rem; color: #4a5568; font-weight: bold; margin-bottom: 0.5rem;\">Colab Backend URL (from Ngrok):</label>
    <input type=\"text\" id=\"apiUrlInput\" value=\"https://upside-shower-handling.ngrok-free.dev\" style=\"width: 100%; padding: 0.5rem; border: 1px solid #cbd5e0; border-radius: 4px; outline: none; transition: border 0.2s;\" onfocus=\"this.style.borderColor='#3182ce'\" onblur=\"this.style.borderColor='#cbd5e0'\">
</div>
<div id=\"customDropZone\" class=\"border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-colors duration-300 relative overflow-hidden border-gray-300 hover:border-blue-400\" style=\"margin: 1rem auto; max-width: 600px; background: white;\">
    <input id=\"customFileInput\" accept=\"image/*,video/*,audio/*\" tabindex=\"-1\" type=\"file\" style=\"display:none;\">
    <div class=\"flex flex-col items-center justify-center text-gray-500\">
        <svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" class=\"lucide lucide-cloud-upload w-16 h-16 mb-4\"><path d=\"M12 13v8\"></path><path d=\"M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242\"></path><path d=\"m8 17 4-4 4 4\"></path></svg>
        <p class=\"text-lg font-semibold\" style=\"color: black; font-size: 1.25rem;\">Drag & drop media or click</p>
        <p class=\"text-sm mt-2\" style=\"color: gray;\">Images, Videos, or Audio</p>
    </div>
</div>
<div id=\"customResults\" style=\"display:none; max-width: 600px; margin: 2rem auto; padding: 1.5rem; background: #fff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center;\">
    <h3 style=\"font-size: 1.5rem; font-weight: bold; margin-bottom: 1rem; color: #333;\">Analysis Result</h3>
    
    <div id=\"progressContainer\" style=\"display:none; margin-bottom: 1.5rem;\">
        <div style=\"width: 100%; background: #e2e8f0; border-radius: 9999px; height: 12px; overflow: hidden;\">
            <div id=\"progressBar\" style=\"height: 100%; width: 0%; background: #3182ce; transition: width 0.3s ease;\"></div>
        </div>
        <p id=\"progressText\" style=\"margin-top: 0.5rem; font-size: 0.9rem; color: #718096;\">Processing...</p>
    </div>

    <div style=\"font-size: 3rem; font-weight: bold; margin-bottom: 0.5rem;\" id=\"customScore\">--</div>
    <div style=\"font-size: 1.1rem; color: #666; margin-bottom: 1rem;\" id=\"customVerdict\">--</div>
    
    <div id=\"breakdownSection\" style=\"display: none; justify-content: space-around; background: #f9f9f9; padding: 1rem; border-radius: 8px;\">
        <div><strong style=\"color:#555\">Visual Forgery:</strong> <span id=\"customVit\">--</span></div>
        <div><strong style=\"color:#555\">Audio Forgery:</strong> <span id=\"customAudio\">--</span></div>
    </div>
</div>
<script>
    const dz = document.getElementById('customDropZone');
    const fi = document.getElementById('customFileInput');
    const res = document.getElementById('customResults');
    const progContainer = document.getElementById('progressContainer');
    const progBar = document.getElementById('progressBar');
    const progText = document.getElementById('progressText');
    const breakdown = document.getElementById('breakdownSection');
    
    dz.addEventListener('click', () => fi.click());
    dz.addEventListener('dragover', (e) => { e.preventDefault(); dz.style.borderColor = 'blue'; });
    dz.addEventListener('dragleave', (e) => { e.preventDefault(); dz.style.borderColor = '#ccc'; });
    dz.addEventListener('drop', (e) => {
        e.preventDefault();
        dz.style.borderColor = '#ccc';
        if (e.dataTransfer.files.length) {
            fi.files = e.dataTransfer.files;
            fi.dispatchEvent(new Event('change'));
        }
    });

    fi.addEventListener('change', async (e) => {
        if (!e.target.files.length) return;
        const file = e.target.files[0];
        
        let apiUrl = document.getElementById('apiUrlInput').value.trim();
        if (apiUrl.endsWith('/')) apiUrl = apiUrl.slice(0, -1);
        
        document.getElementById('customScore').textContent = 'Queued...';
        document.getElementById('customScore').style.color = '#333';
        document.getElementById('customVerdict').textContent = 'Uploading to server';
        res.style.display = 'block';
        progContainer.style.display = 'block';
        breakdown.style.display = 'none';
        progBar.style.width = '10%';
        
        const fd = new FormData();
        fd.append('file', file);
        try {
            const r = await fetch(apiUrl + '/detect', {
                method: 'POST',
                headers: {'ngrok-skip-browser-warning': 'true'},
                body: fd
            });
            const data = await r.json();
            
            if (data.task_id) {
                // Async Celery Polling
                const taskId = data.task_id;
                let pollInterval = setInterval(async () => {
                    try {
                        const statusRes = await fetch(apiUrl + '/status/' + taskId, {
                            headers: {'ngrok-skip-browser-warning': 'true'}
                        });
                        const statusData = await statusRes.json();
                        
                        if (statusData.state === 'SUCCESS' || statusData.result) {
                            clearInterval(pollInterval);
                            progContainer.style.display = 'none';
                            breakdown.style.display = 'flex';
                            
                            const result = statusData.result;
                            const fusion = (result.confidence * 100).toFixed(1);
                            document.getElementById('customScore').textContent = fusion + '%';
                            document.getElementById('customScore').style.color = fusion > 50 ? '#e53e3e' : '#38a169';
                            document.getElementById('customVerdict').textContent = result.is_fake ? 'Synthetic Deepfake Detected' : 'Authentic Media Verified';
                            document.getElementById('customVit').textContent = (result.breakdown && result.breakdown.visual_score !== null) ? (result.breakdown.visual_score * 100).toFixed(1) + '%' : 'N/A';
                            document.getElementById('customAudio').textContent = (result.breakdown && result.breakdown.audio_score !== null) ? (result.breakdown.audio_score * 100).toFixed(1) + '%' : 'N/A';
                        } else if (statusData.state === 'FAILURE') {
                            clearInterval(pollInterval);
                            progContainer.style.display = 'none';
                            document.getElementById('customScore').textContent = 'Error';
                            document.getElementById('customVerdict').textContent = 'Processing Failed on Server';
                        } else if (statusData.state === 'PROGRESS' && statusData.status) {
                            progBar.style.width = statusData.status.progress + '%';
                            progText.textContent = statusData.status.step || 'Processing...';
                        }
                    } catch (pollErr) {
                        console.error('Polling error', pollErr);
                    }
                }, 2000);
            } else {
                // Synchronous processing fallback (if Celery was bypassed)
                progContainer.style.display = 'none';
                breakdown.style.display = 'flex';
                
                const fusion = (data.fusion_score * 100).toFixed(1);
                document.getElementById('customScore').textContent = fusion + '%';
                document.getElementById('customScore').style.color = fusion > 50 ? '#e53e3e' : '#38a169';
                document.getElementById('customVerdict').textContent = fusion > 50 ? 'Synthetic Deepfake Detected' : 'Authentic Media Verified';
                document.getElementById('customVit').textContent = data.vision_fake_probability !== null ? (data.vision_fake_probability * 100).toFixed(1) + '%' : 'N/A';
                document.getElementById('customAudio').textContent = data.audio_fake_probability !== null ? (data.audio_fake_probability * 100).toFixed(1) + '%' : 'N/A';
            }
        } catch(err) {
            progContainer.style.display = 'none';
            document.getElementById('customScore').textContent = 'Error';
            document.getElementById('customVerdict').textContent = 'Could not connect to API (Check Ngrok URL)';
        }
    });
</script>
"""
if '<main' in html:
    html = html.replace('<main', dropzone_html + '<main', 1)
elif '<header' in html:
    html = html.replace('</header>', '</header>' + dropzone_html, 1)
else:
    html = html.replace('<body>', '<body>' + dropzone_html, 1)
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)
