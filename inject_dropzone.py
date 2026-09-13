import re

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

dropzone_html = '''
<div id="customDropZone" class="border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-colors duration-300 relative overflow-hidden border-gray-300 hover:border-blue-400" style="margin: 2rem auto; max-width: 600px; background: white;">
    <input id="customFileInput" accept="image/*,video/*,audio/*" tabindex="-1" type="file" style="display:none;">
    <div class="flex flex-col items-center justify-center text-gray-500">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-cloud-upload w-16 h-16 mb-4"><path d="M12 13v8"></path><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"></path><path d="m8 17 4-4 4 4"></path></svg>
        <p class="text-lg font-semibold" style="color: black; font-size: 1.25rem;">Drag & drop an image or click</p>
        <p class="text-sm mt-2" style="color: gray;">PNG, JPG, WEBP, MP4, MP3 up to 15 MB</p>
    </div>
</div>
<div id="customResults" style="display:none; max-width: 600px; margin: 2rem auto; padding: 1.5rem; background: #fff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center;">
    <h3 style="font-size: 1.5rem; font-weight: bold; margin-bottom: 1rem; color: #333;">Analysis Result</h3>
    <div style="font-size: 3rem; font-weight: bold; margin-bottom: 0.5rem;" id="customScore">--</div>
    <div style="font-size: 1.1rem; color: #666; margin-bottom: 1rem;" id="customVerdict">--</div>
    <div style="display: flex; justify-content: space-around; background: #f9f9f9; padding: 1rem; border-radius: 8px;">
        <div><strong style="color:#555">Vision Fake:</strong> <span id="customVit">--</span></div>
        <div><strong style="color:#555">Audio Fake:</strong> <span id="customAudio">--</span></div>
    </div>
</div>
<script>
    const dz = document.getElementById('customDropZone');
    const fi = document.getElementById('customFileInput');
    const res = document.getElementById('customResults');
    
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
        
        document.getElementById('customScore').textContent = 'Analyzing...';
        document.getElementById('customVerdict').textContent = 'Please wait';
        res.style.display = 'block';
        
        const fd = new FormData();
        fd.append('file', file);
        try {
            const r = await fetch('https://upside-shower-handling.ngrok-free.dev/detect', {
                method: 'POST',
                headers: {'ngrok-skip-browser-warning': 'true'},
                body: fd
            });
            const data = await r.json();
            const fusion = (data.fusion_score * 100).toFixed(1);
            document.getElementById('customScore').textContent = fusion + '%';
            document.getElementById('customScore').style.color = fusion > 50 ? '#e53e3e' : '#38a169';
            document.getElementById('customVerdict').textContent = fusion > 50 ? 'Synthetic Deepfake' : 'Authentic Media';
            document.getElementById('customVit').textContent = data.vision_fake_probability !== null ? (data.vision_fake_probability * 100).toFixed(1) + '%' : 'N/A';
            document.getElementById('customAudio').textContent = data.audio_fake_probability !== null ? (data.audio_fake_probability * 100).toFixed(1) + '%' : 'N/A';
        } catch(err) {
            document.getElementById('customScore').textContent = 'Error';
            document.getElementById('customVerdict').textContent = 'Could not connect to API';
        }
    });
</script>
'''

# Inject right after the header or at the start of the body
if '<main' in html:
    html = html.replace('<main', dropzone_html + '<main', 1)
elif '<header' in html:
    html = html.replace('</header>', '</header>' + dropzone_html, 1)
else:
    html = html.replace('<body>', '<body>' + dropzone_html, 1)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)
