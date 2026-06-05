/**
 * Alert WebSocket Service
 * Connects to Django Channels ws…/ws/alerts/ for real-time alert notifications
 */

import { getChannelsWebSocketUrl } from './apiConfig'

export class AlertWebSocketService {
    constructor() {
        this.ws = null
        this.url = null
        this.listeners = []
        this.connected = false
        this.reconnectAttempts = 0
        this.maxReconnectAttempts = 5
        this.reconnectDelay = 3000
    }

    /**
     * Connect to the alerts WebSocket
     * @param {Function} onAlert - Callback when new alert is received
     */
    connect(onAlert) {
        this.url = getChannelsWebSocketUrl('/ws/alerts/')

        console.log('[ALERT_WS] Connecting to', this.url)

        try {
            this.ws = new WebSocket(this.url)

            this.ws.onopen = () => {
                console.log('[ALERT_WS] ✅ Connected to alert stream')
                this.connected = true
                this.reconnectAttempts = 0
            }

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data)
                    console.log('[ALERT_WS] Received:', data)

                    if (onAlert) {
                        onAlert(data)
                    }

                    // Call all registered listeners
                    this.listeners.forEach(listener => {
                        try {
                            listener(data)
                        } catch (err) {
                            console.warn('[ALERT_WS] Listener error:', err)
                        }
                    })
                } catch (err) {
                    console.warn('[ALERT_WS] Failed to parse message:', err)
                }
            }

            this.ws.onerror = (error) => {
                console.error('[ALERT_WS] WebSocket error:', error)
            }

            this.ws.onclose = () => {
                console.warn('[ALERT_WS] Disconnected. Attempting to reconnect...')
                this.connected = false
                this.attemptReconnect(onAlert)
            }
        } catch (err) {
            console.error('[ALERT_WS] Failed to connect:', err)
            this.attemptReconnect(onAlert)
        }
    }

    /**
     * Attempt to reconnect with exponential backoff
     */
    attemptReconnect(onAlert) {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('[ALERT_WS] Max reconnection attempts reached. Giving up.')
            return
        }

        this.reconnectAttempts++
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
        console.log(`[ALERT_WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)

        setTimeout(() => {
            this.connect(onAlert)
        }, delay)
    }

    /**
     * Add a listener for alert events
     */
    addListener(listener) {
        this.listeners.push(listener)
    }

    /**
     * Remove a listener
     */
    removeListener(listener) {
        this.listeners = this.listeners.filter(l => l !== listener)
    }

    /**
     * Disconnect from WebSocket
     */
    disconnect() {
        if (this.ws) {
            console.log('[ALERT_WS] Disconnecting...')
            this.ws.close()
            this.ws = null
            this.connected = false
        }
    }

    /**
     * Check if connected
     */
    isConnected() {
        return this.connected
    }
}

// Export singleton instance
export const alertWebSocket = new AlertWebSocketService()
