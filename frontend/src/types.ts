export interface SystemStats {
    cpu: number;
    memory: {
        total: number;
        available: number;
        percent: number;
    };
    disk: {
        total: number;
        free: number;
        percent: number;
    };
    net: {
        sent: number;
        recv: number;
    };
}

export interface UrlStatus {
    name: string;
    url: string;
    status: 'up' | 'down';
    status_code: number;
    error?: string | null;
    checked_at?: string;
}

export interface WebSocketPayload {
    type: string;
    system: SystemStats;
    urls: UrlStatus[];
}
