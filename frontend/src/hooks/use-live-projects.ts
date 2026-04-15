"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { projectsAPI } from "@/lib/api";
import { isActiveProjectStatus, mergeProjectStatus } from "@/lib/project-live";

type UseLiveProjectsOptions = {
    intervalMs?: number;
};

export function useLiveProjects(options: UseLiveProjectsOptions = {}) {
    const { intervalMs = 2000 } = options;
    const [projects, setProjects] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const inFlightRef = useRef(false);
    const mountedRef = useRef(true);

    const refreshProjects = useCallback(async () => {
        if (inFlightRef.current) {
            return;
        }

        inFlightRef.current = true;
        try {
            const res = await projectsAPI.list();
            const listedProjects = Array.isArray(res.data) ? res.data : [];
            const activeProjects = listedProjects.filter((project: any) => isActiveProjectStatus(project.status));

            if (activeProjects.length === 0) {
                if (mountedRef.current) {
                    setProjects(listedProjects);
                }
                return;
            }

            const statuses = await Promise.all(
                activeProjects.map(async (project: any) => {
                    try {
                        const statusRes = await projectsAPI.getStatus(project.id);
                        return [project.id, statusRes.data] as const;
                    } catch {
                        return [project.id, null] as const;
                    }
                })
            );

            const statusMap = new Map(statuses);
            const hydratedProjects = listedProjects.map((project: any) =>
                mergeProjectStatus(project, statusMap.get(project.id) ?? null)
            );

            if (mountedRef.current) {
                setProjects(hydratedProjects);
            }
        } catch (err) {
            console.error("Failed to load projects:", err);
        } finally {
            if (mountedRef.current) {
                setLoading(false);
            }
            inFlightRef.current = false;
        }
    }, []);

    useEffect(() => {
        mountedRef.current = true;

        refreshProjects();
        const interval = window.setInterval(refreshProjects, intervalMs);
        const handleVisibility = () => {
            if (document.visibilityState === "visible") {
                refreshProjects();
            }
        };

        window.addEventListener("focus", refreshProjects);
        document.addEventListener("visibilitychange", handleVisibility);

        return () => {
            mountedRef.current = false;
            window.clearInterval(interval);
            window.removeEventListener("focus", refreshProjects);
            document.removeEventListener("visibilitychange", handleVisibility);
        };
    }, [intervalMs, refreshProjects]);

    return {
        projects,
        setProjects,
        loading,
        refreshProjects,
    };
}
