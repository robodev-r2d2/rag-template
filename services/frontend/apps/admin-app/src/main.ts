import { i18n } from '@i18n/admin';
import '@shared/style';
import { createPinia } from 'pinia';
import { createApp } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
import App from './App.vue';
import { routes } from './routes';

import { authService } from '@shared/auth/auth.service';

export async function setupApp() {
  // Initialize Auth
  const user = await authService.getUser();
  if (!user) {
    if (window.location.pathname !== '/callback') {
      await authService.login();
      return;
    } else {
      await authService.handleCallback();
      window.location.href = '/';
      return;
    }
  }

  const router = createRouter({
    history: createWebHistory("/"),
    routes
  });

  const app = createApp(App).use(i18n).use(createPinia());

  app.use(router);
  await router.isReady();

  app.mount('#app');
  return app;
}
setupApp();
