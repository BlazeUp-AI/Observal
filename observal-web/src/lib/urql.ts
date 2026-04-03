import { createClient, fetchExchange, subscriptionExchange } from 'urql';
import { createClient as createWSClient } from 'graphql-ws';

const wsClient = createWSClient({
  url: `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/v1/graphql`,
});

export const client = createClient({
  url: '/api/v1/graphql',
  exchanges: [
    fetchExchange,
    subscriptionExchange({
      forwardSubscription(request) {
        const input = { ...request, query: request.query || '' };
        return {
          subscribe(sink) {
            const unsubscribe = wsClient.subscribe(input, sink);
            return { unsubscribe };
          },
        };
      },
    }),
  ],
});
