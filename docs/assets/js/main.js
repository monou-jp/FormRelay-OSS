// Main JS for FormRelay Landing Page

document.addEventListener('DOMContentLoaded', () => {
    // Smooth scrolling for all anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href === '#') return;
            
            e.preventDefault();
            const target = document.querySelector(href);
            if (target) {
                const headerOffset = 0;
                const elementPosition = target.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

                window.scrollTo({
                    top: offsetPosition,
                    behavior: "smooth"
                });
            }
        });
    });

    // Intersection Observer for scroll animations
    const observerOptions = {
        threshold: 0.15,
        rootMargin: "0px 0px -50px 0px"
    };

    const revealOnScroll = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('opacity-100', 'translate-y-0');
                entry.target.classList.remove('opacity-0', 'translate-y-10');
                revealOnScroll.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Apply animation classes and observe
    const animateElements = [
        ...document.querySelectorAll('.feature-card'),
        ...document.querySelectorAll('section h2'),
        ...document.querySelectorAll('.code-window'),
        ...document.querySelectorAll('table')
    ];

    animateElements.forEach(el => {
        el.classList.add('transition-all', 'duration-1000', 'opacity-0', 'translate-y-10');
        revealOnScroll.observe(el);
    });

    // Tab switch logic for advanced config section (if added)
    const tabs = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.tab;
            
            tabs.forEach(t => t.classList.remove('active', 'border-indigo-600', 'text-indigo-600'));
            tabContents.forEach(c => c.classList.add('hidden'));
            
            tab.classList.add('active', 'border-indigo-600', 'text-indigo-600');
            document.getElementById(`tab-${target}`).classList.remove('hidden');
        });
    });
});
