JSON.stringify([...document.querySelectorAll('[role=dialog],dialog')].map(d => (d.innerText||'').replace(/\s+/g,' ').slice(0,1500)))
