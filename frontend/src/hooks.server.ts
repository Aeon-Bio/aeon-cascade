import type { Handle } from '@sveltejs/kit';

const BACKEND_URL = process.env.PUBLIC_API_URL || 'http://localhost:8000';

export const handle: Handle = async ({ event, resolve }) => {
	const { pathname } = event.url;

	// Proxy API and health requests to backend
	if (pathname.startsWith('/api/') || pathname === '/health' || pathname === '/docs' || pathname === '/openapi.json') {
		const backendUrl = `${BACKEND_URL}${pathname}${event.url.search}`;

		try {
			const response = await fetch(backendUrl, {
				method: event.request.method,
				headers: event.request.headers,
				body: event.request.method !== 'GET' && event.request.method !== 'HEAD'
					? await event.request.text()
					: undefined,
			});

			const headers = new Headers(response.headers);
			// Preserve important headers
			if (!headers.has('access-control-allow-origin')) {
				headers.set('access-control-allow-origin', '*');
			}

			return new Response(response.body, {
				status: response.status,
				statusText: response.statusText,
				headers
			});
		} catch (error) {
			console.error(`Failed to proxy request to backend: ${error}`);
			return new Response(JSON.stringify({ error: 'Backend unavailable' }), {
				status: 503,
				headers: { 'content-type': 'application/json' }
			});
		}
	}

	// Normal SvelteKit routing for all other requests
	return resolve(event);
};
