(function(){
  const form = document.getElementById('ack-form');
  const status = document.getElementById('ack-status');
  const lightbox = document.getElementById('lightbox');
  const lightboxImg = document.querySelector('.lightbox__img');

  const PHONE = '5492920591019';
  const APIKEY = '4823463';

  function urlencode(text){
    return encodeURIComponent(text).replace(/%20/g, '+');
  }

  function sendWhatsApp(text){
    // Evitar CORS: usamos una imagen con la URL del GET
    const url = `https://api.callmebot.com/whatsapp.php?phone=${PHONE}&text=${urlencode(text)}&apikey=${APIKEY}`;
    const img = new Image();
    img.onload = function(){
      status.textContent = 'Confirmación enviada. ¡Gracias!';
      status.style.color = '#10b981';
      form.reset();
    };
    // Muchos endpoints devuelven text/plain, lo que dispara onerror en <img>,
    // aunque el mensaje se haya enviado. Consideramos onerror como éxito lógico.
    img.onerror = function(){
      status.textContent = 'Confirmación enviada (respuesta no verificable por el navegador).';
      status.style.color = '#10b981';
      form.reset();
    };
    img.src = url + `&t=${Date.now()}`; // cache-buster
  }

  form.addEventListener('submit', function(e){
    e.preventDefault();
    const nombre = document.getElementById('nombre').value.trim();
    const apellido = document.getElementById('apellido').value.trim();
    const anydesk = document.getElementById('anydesk').value.trim();
    const local = document.getElementById('local').value.trim();
    const passdesk = document.getElementById('passdesk').value.trim();
    const acepto = document.getElementById('acepto').checked;

    if(!nombre || !apellido || !local || !anydesk || !acepto){
      status.textContent = 'Complete nombre, apellido, local, ID de AnyDesk y acepte la confirmación.';
      status.style.color = '#ef4444';
      return;
    }

    const passPart = passdesk ? ` (pass: ${passdesk})` : '';
    const texto = `Tutorial Picking (${local}): ${nombre} ${apellido} confirmó lectura y entendimiento. AnyDesk: ${anydesk}${passPart}.`;
    status.textContent = 'Enviando confirmación…';
    status.style.color = '#9ca3af';
    sendWhatsApp(texto);
  });

  // Lightbox
  document.querySelectorAll('img.zoomable').forEach(img => {
    img.addEventListener('click', () => {
      lightboxImg.src = img.src;
      lightbox.setAttribute('aria-hidden', 'false');
    });
  });
  lightbox.addEventListener('click', () => {
    lightbox.setAttribute('aria-hidden', 'true');
    lightboxImg.src = '';
  });
})();
