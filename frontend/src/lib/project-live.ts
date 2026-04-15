export const ACTIVE_PROJECT_STATUSES = new Set([
    "UPLOADED",
    "TRANSCRIBING",
    "ANALYZING",
    "GENERATING_CLIPS",
]);

export const TERMINAL_PROJECT_STATUSES = new Set(["COMPLETED", "FAILED"]);

export function isActiveProjectStatus(status?: string | null) {
    return status ? ACTIVE_PROJECT_STATUSES.has(status) : false;
}

export function isTerminalProjectStatus(status?: string | null) {
    return status ? TERMINAL_PROJECT_STATUSES.has(status) : false;
}

export function mergeProjectStatus<T extends Record<string, any>>(project: T, statusPayload?: Record<string, any> | null): T {
    if (!statusPayload) {
        return project;
    }

    return {
        ...project,
        status: statusPayload.status ?? project.status,
        progress: statusPayload.progress ?? project.progress,
        status_message: statusPayload.status_message ?? project.status_message,
        error_message: statusPayload.error_message ?? project.error_message,
    };
}
