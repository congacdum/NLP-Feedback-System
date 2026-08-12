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

/* -- Inline Feedback Assistant -- */
const feedbackFab = document.querySelector('[data-feedback-fab]');
const feedbackPanel = document.querySelector('[data-feedback-panel]');
const feedbackForm = document.querySelector('[data-feedback-form]');
const feedbackContext = document.querySelector('[data-feedback-context]');
const feedbackScrollArea = document.querySelector('[data-feedback-scroll-area]');
const feedbackStatus = document.querySelector('[data-feedback-status]');
const feedbackConversation = document.querySelector('[data-feedback-conversation]');
const feedbackCustomerTurn = document.querySelector('[data-feedback-customer-turn]');
const feedbackCustomerMessage = document.querySelector('[data-feedback-customer-message]');
const feedbackRating = document.querySelector('[data-feedback-rating]');
const feedbackAssistantTurn = document.querySelector('[data-feedback-assistant-turn]');
const feedbackResponseLabel = document.querySelector('[data-feedback-response-label]');
const feedbackSubmit = document.querySelector('[data-feedback-submit]');
const feedbackProductRoot = document.querySelector('[data-feedback-product-id]');
const feedbackProductId = feedbackProductRoot ? Number(feedbackProductRoot.dataset.feedbackProductId) : null;
const feedbackProductName = feedbackProductRoot?.dataset.feedbackProductName || '';

function showFeedbackStatus(message, kind = 'info') {
  if (!feedbackStatus || !feedbackConversation) return;
  feedbackConversation.classList.remove('hidden');
  if (feedbackAssistantTurn) feedbackAssistantTurn.classList.remove('hidden');
  const bubble = feedbackAssistantTurn?.firstElementChild;
  if (bubble) {
    bubble.className = `max-w-[90%] rounded-2xl rounded-bl-md border px-3 py-2.5 text-sm shadow-sm ${
      kind === 'success' ? 'border-emerald-100 bg-emerald-50 text-emerald-900' :
      kind === 'error' ? 'border-rose-100 bg-rose-50 text-rose-900' :
      'border-indigo-100 bg-indigo-50 text-indigo-900'
    }`;
  }
  if (feedbackResponseLabel) {
    feedbackResponseLabel.className = `mb-1 text-xs font-semibold ${
      kind === 'success' ? 'text-emerald-700' : kind === 'error' ? 'text-rose-700' : 'text-indigo-700'
    }`;
    feedbackResponseLabel.textContent = kind === 'success' ? 'Trợ lý phản hồi' : kind === 'error' ? 'Không thể gửi đánh giá' : 'Trợ lý đang phản hồi';
  }
  feedbackStatus.textContent = message;
  requestAnimationFrame(() => {
    if (feedbackScrollArea) feedbackScrollArea.scrollTop = feedbackScrollArea.scrollHeight;
  });
}

function renderCustomerFeedback(rating, message) {
  if (!feedbackConversation || !feedbackCustomerTurn || !feedbackCustomerMessage || !feedbackRating) return;
  feedbackConversation.classList.remove('hidden');
  feedbackCustomerTurn.classList.remove('hidden');
  feedbackRating.textContent = `Đánh giá ${rating}/5`;
  feedbackCustomerMessage.textContent = message;
}

function clearFeedbackConversation() {
  if (feedbackConversation) feedbackConversation.classList.add('hidden');
  if (feedbackCustomerTurn) feedbackCustomerTurn.classList.add('hidden');
  if (feedbackAssistantTurn) feedbackAssistantTurn.classList.add('hidden');
  if (feedbackCustomerMessage) feedbackCustomerMessage.textContent = '';
  if (feedbackRating) feedbackRating.textContent = '';
  if (feedbackStatus) feedbackStatus.textContent = '';
  if (feedbackResponseLabel) feedbackResponseLabel.textContent = '';
}

function openFeedbackForm() {
  if (!feedbackPanel) return;
  feedbackPanel.classList.add('open');
  clearFeedbackConversation();
  if (!feedbackProductId) {
    if (feedbackForm) feedbackForm.classList.add('hidden');
    if (feedbackContext) feedbackContext.textContent = 'Mở trang chi tiết sản phẩm để gửi đánh giá.';
    return;
  }
  if (feedbackForm) feedbackForm.classList.remove('hidden');
  if (feedbackContext) {
    feedbackContext.textContent = `Bạn đang đánh giá: ${feedbackProductName || 'sản phẩm này'}. Hãy chọn số sao và chia sẻ trải nghiệm của bạn.`;
  }
}

if (feedbackFab && feedbackPanel) {
  feedbackFab.addEventListener('click', () => {
    if (feedbackPanel.classList.contains('open')) {
      feedbackPanel.classList.remove('open');
    } else {
      openFeedbackForm();
    }
  });
}

document.querySelectorAll('[data-open-feedback-form]').forEach(button =>
  button.addEventListener('click', openFeedbackForm)
);

if (feedbackForm) {
  feedbackForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (!feedbackProductId) {
      showFeedbackStatus('Hãy mở trang chi tiết sản phẩm trước khi gửi đánh giá.', 'error');
      return;
    }

    const values = new FormData(feedbackForm);
    const rating = Number(values.get('rating'));
    const text = String(values.get('text') || '').trim();
    if (!rating || !text) return;

    feedbackSubmit.disabled = true;
    feedbackSubmit.textContent = 'Đang lưu và phân tích...';
    renderCustomerFeedback(rating, text);
    showFeedbackStatus('Đang ghi nhận feedback của bạn...');

    try {
      const response = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: feedbackProductId, rating, text }),
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : '';
        throw new Error(data.message || detail || 'Không thể gửi đánh giá lúc này.');
      }

      showFeedbackStatus(data.assistant_message || 'Cảm ơn bạn đã chia sẻ. Phản hồi của bạn đã được ghi nhận.', 'success');
      feedbackForm.reset();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Không thể gửi đánh giá lúc này.';
      showFeedbackStatus(message === 'Login required' ? 'Bạn cần đăng nhập bằng tài khoản khách hàng để gửi đánh giá.' : message, 'error');
    } finally {
      feedbackSubmit.disabled = false;
      feedbackSubmit.textContent = 'Gửi đánh giá';
    }
  });
}

/* -- Seller Nav Active State -- */
const currentPath = window.location.pathname;
document.querySelectorAll('.seller-nav a').forEach(link => {
  const href = link.getAttribute('href');
  if (href === currentPath || (href === '/seller' && currentPath === '/seller')) {
    link.classList.add('active');
  }
});
