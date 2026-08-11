/* -- Image Loading -- */
const fallback = '/static/img/product-placeholder.svg';
document.querySelectorAll('img[data-product-image]').forEach((img, i) => {
  img.onerror = () => { img.onerror = null; img.src = fallback };
  if (i < 6) { img.loading = 'eager'; img.fetchPriority = 'high' } else { img.loading = 'lazy' }
  img.decoding = 'async'
});

const lazy = [...document.querySelectorAll('img[data-lazy-src]')];
if ('IntersectionObserver' in window) {
  const io = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.src = entry.target.dataset.lazySrc;
        delete entry.target.dataset.lazySrc;
        io.unobserve(entry.target)
      }
    })
  }, { rootMargin: '400px' });
  lazy.forEach(image => io.observe(image))
} else {
  lazy.forEach(image => { image.src = image.dataset.lazySrc })
}

/* -- Scroll-triggered Animations -- */
const animatedElements = document.querySelectorAll('.animate-fade-in-up');
if ('IntersectionObserver' in window && animatedElements.length) {
  const animObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.animationPlayState = 'running';
        animObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });
  animatedElements.forEach(el => {
    el.style.animationPlayState = 'paused';
    animObserver.observe(el);
  });
}

/* -- Header Scroll Effect -- */
const siteHeader = document.getElementById('site-header');
if (siteHeader) {
  let lastScrollY = 0;
  const onScroll = () => {
    const scrollY = window.scrollY;
    if (scrollY > 40) {
      siteHeader.classList.add('scrolled');
    } else {
      siteHeader.classList.remove('scrolled');
    }
    lastScrollY = scrollY;
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

/* -- Mobile Navigation -- */
const navToggle = document.querySelector('[data-nav-toggle]');
const primaryNav = document.querySelector('[data-primary-nav]');
if (navToggle && primaryNav) {
  navToggle.addEventListener('click', () => {
    const open = primaryNav.classList.toggle('mobile-open');
    navToggle.setAttribute('aria-expanded', String(open));
  });
  primaryNav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
    primaryNav.classList.remove('mobile-open');
    navToggle.setAttribute('aria-expanded', 'false');
  }));
}

/* -- Chat Widget -- */
const fab = document.querySelector('[data-chat-fab]'),
  panel = document.querySelector('[data-chat-panel]'),
  form = document.querySelector('[data-chat-form]'),
  body = document.querySelector('[data-chat-body]');
const productRoot = document.querySelector('[data-chat-product-id]');
const productId = productRoot ? Number(productRoot.dataset.chatProductId) : null;
const chatSender = (() => {
  const key = 'nlp-feedback-chat-sender';
  let value = localStorage.getItem(key);
  if (!value) {
    value = 'web-' + (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36));
    localStorage.setItem(key, value)
  }
  return value
})();

let activeProductId = null;
let contextCard = null;

function bubble(text, me = false) {
  if (!body) return;
  const element = document.createElement('div');
  element.className = 'bubble' + (me ? ' me' : '');
  element.textContent = text;
  body.appendChild(element);
  body.scrollTop = body.scrollHeight
}

function showTyping() {
  if (!body) return null;
  const el = document.createElement('div');
  el.className = 'bubble typing-indicator';
  el.innerHTML = '<span></span><span></span><span></span>';
  body.appendChild(el);
  body.scrollTop = body.scrollHeight;
  return el;
}

function priceLabel(price) {
  return Number(price) > 0 ? new Intl.NumberFormat('vi-VN').format(Number(price)) + ' ₫' : 'Chưa có dữ liệu giá'
}

function renderProductContext(product) {
  if (!panel || !product) return;
  if (!contextCard) {
    contextCard = document.createElement('section');
    contextCard.className = 'chat-product-context';
    body?.before(contextCard)
  }
  contextCard.replaceChildren();
  const label = document.createElement('div');
  label.className = 'chat-product-context-label';
  label.textContent = 'Sản phẩm đang trao đổi';
  const row = document.createElement('div');
  row.className = 'chat-product-context-row';
  const image = document.createElement('img');
  image.src = product.image_url || fallback;
  image.alt = product.product_name || 'Sản phẩm';
  image.onerror = () => { image.onerror = null; image.src = fallback };
  const details = document.createElement('div');
  const name = document.createElement('strong');
  name.textContent = product.product_name || 'Sản phẩm';
  const price = document.createElement('span');
  price.textContent = priceLabel(product.price);
  details.append(name, price);
  row.append(image, details);
  contextCard.append(label, row);
}

async function startProductChat() {
  if (!productId || !panel) return false;
  if (activeProductId === productId) {
    panel.classList.add('open');
    return true
  }
  try {
    const response = await fetch('/api/chat/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sender: chatSender, product_id: productId })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Không thể bắt đầu trao đổi');

    activeProductId = productId;
    renderProductContext(data.product);
    panel.classList.add('open');

    const productName = data.product?.product_name || 'sản phẩm';
    const welcomeText = `Chào bạn! Bạn cần hỗ trợ hoặc có phản hồi gì về "${productName}" không?`;
    bubble(welcomeText);
    return true;
  } catch (_) {
    panel.classList.add('open');
    bubble('Chưa thể kết nối lúc này. Bạn thử lại giúp mình nhé.');
    return false
  }
}

if (fab && panel) {
  fab.onclick = async () => {
    const opening = !panel.classList.contains('open');
    panel.classList.toggle('open');
    if (opening && productId && !activeProductId) await startProductChat()
  }
}

document.querySelectorAll('[data-open-product-chat]').forEach(button =>
  button.addEventListener('click', startProductChat)
);

if (form) {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const input = form.querySelector('input');
    const text = input.value.trim();
    if (!text) return;
    if (productId && !(await startProductChat())) return;

    bubble(text, true);
    input.value = '';

    const typingEl = showTyping();

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, sender: chatSender, product_id: productId })
      });
      const data = await response.json();
      if (typingEl) typingEl.remove();
      bubble(data.text || 'Cảm ơn phản hồi của bạn!')
    } catch (_) {
      if (typingEl) typingEl.remove();
      bubble('Không thể kết nối chatbot lúc này.')
    }
  })
}

/* -- Seller Nav Active State -- */
const currentPath = window.location.pathname;
document.querySelectorAll('.seller-nav a').forEach(link => {
  const href = link.getAttribute('href');
  if (href === currentPath || (href === '/seller' && currentPath === '/seller')) {
    link.classList.add('active');
  }
});
