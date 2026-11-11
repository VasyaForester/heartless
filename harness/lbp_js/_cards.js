JSON.stringify([...document.querySelectorAll('button')].filter(b => (b.innerText||'').includes('Broken at least once')).map(b => (b.innerText||'').replace(/\s+/g,' ').slice(0,100)))
