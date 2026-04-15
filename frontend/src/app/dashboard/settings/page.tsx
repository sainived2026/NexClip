"use client";

import { Settings as SettingsIcon } from "lucide-react";

export default function SettingsPage() {
    return (
        <div>
            <div className="mb-8">
                <h1 className="text-2xl font-bold text-white">Settings</h1>
                <p className="text-sm text-[var(--nc-text-muted)] mt-1">Manage your account preferences</p>
            </div>

            <div className="max-w-xl space-y-6">
                <div className="p-6 rounded-2xl glass">
                    <h2 className="text-sm font-medium text-[var(--nc-text-muted)] uppercase tracking-wider mb-4">Profile</h2>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm text-[var(--nc-text-muted)] mb-1.5">Display Name</label>
                            <input type="text" className="w-full px-4 py-2.5 rounded-lg bg-[var(--nc-bg)] border border-[var(--nc-border)] text-white text-sm focus:outline-none focus:border-indigo-500 transition-colors" placeholder="John Doe" />
                        </div>
                        <div>
                            <label className="block text-sm text-[var(--nc-text-muted)] mb-1.5">Email</label>
                            <input type="email" className="w-full px-4 py-2.5 rounded-lg bg-[var(--nc-bg)] border border-[var(--nc-border)] text-white text-sm focus:outline-none focus:border-indigo-500 transition-colors" placeholder="john@example.com" />
                        </div>
                    </div>
                    <button className="mt-4 px-4 py-2 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-medium transition-all hover:shadow-lg hover:shadow-indigo-500/25">
                        Save Changes
                    </button>
                </div>

                <div className="p-6 rounded-2xl glass">
                    <h2 className="text-sm font-medium text-[var(--nc-text-muted)] uppercase tracking-wider mb-4">Preferences</h2>
                    <div className="space-y-3">
                        <label className="flex items-center justify-between cursor-pointer">
                            <span className="text-sm text-[var(--nc-text-muted)]">Default clip count</span>
                            <select defaultValue="10" className="px-3 py-1.5 rounded-lg bg-[var(--nc-bg)] border border-[var(--nc-border)] text-white text-sm focus:outline-none">
                                <option value="5">5</option>
                                <option value="10">10</option>
                                <option value="15">15</option>
                                <option value="20">20</option>
                            </select>
                        </label>
                        <label className="flex items-center justify-between cursor-pointer">
                            <span className="text-sm text-[var(--nc-text-muted)]">Email notifications</span>
                            <div className="w-10 h-5 rounded-full bg-indigo-500 relative cursor-pointer">
                                <div className="absolute right-0.5 top-0.5 w-4 h-4 rounded-full bg-white transition-all" />
                            </div>
                        </label>
                    </div>
                </div>
            </div>
        </div>
    );
}
