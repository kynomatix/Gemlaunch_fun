/**
 * Vesting Utilities Module
 * Shared formatting and calculation functions for PRO token vesting
 */

const VestingUtils = {
    /**
     * Vesting schedule configurations
     */
    VESTING_SCHEDULES: {
        marketing: {
            cliff: 0,
            duration: 365 * 24 * 60 * 60,
            label: 'Marketing',
            description: 'Linear unlock over 12 months, no cliff'
        },
        team: {
            cliff: 180 * 24 * 60 * 60,
            duration: 730 * 24 * 60 * 60,
            label: 'Team',
            description: '6-month cliff, then linear unlock over 24 months'
        },
        airdrops: {
            cliff: 30 * 24 * 60 * 60,
            duration: 90 * 24 * 60 * 60,
            label: 'Airdrops',
            description: '1-month cliff, then linear unlock over 3 months'
        }
    },

    /**
     * Format vesting unlock schedule in human-readable format
     * @param {string} vestingType - 'marketing' | 'team' | 'airdrops'
     * @param {number} startTime - Unix timestamp of vesting start
     * @param {number} duration - Duration in seconds (optional, uses default if not provided)
     * @returns {string} Human-readable schedule
     */
    formatUnlockSchedule(vestingType, startTime, duration = null) {
        const schedule = this.VESTING_SCHEDULES[vestingType];
        if (!schedule) return 'Unknown schedule';

        const actualDuration = duration || schedule.duration;
        const cliffDays = Math.floor(schedule.cliff / (24 * 60 * 60));
        const durationDays = Math.floor(actualDuration / (24 * 60 * 60));
        
        if (schedule.cliff === 0) {
            return `Linear unlock over ${this.formatDuration(actualDuration)}`;
        } else {
            return `${this.formatDuration(schedule.cliff)} cliff, then linear unlock over ${this.formatDuration(actualDuration)}`;
        }
    },

    /**
     * Format duration in human-readable format
     * @param {number} seconds - Duration in seconds
     * @returns {string} Human-readable duration
     */
    formatDuration(seconds) {
        const days = Math.floor(seconds / (24 * 60 * 60));
        const months = Math.floor(days / 30);
        const years = Math.floor(days / 365);

        if (years > 0) {
            return years === 1 ? '1 year' : `${years} years`;
        } else if (months > 0) {
            return months === 1 ? '1 month' : `${months} months`;
        } else {
            return days === 1 ? '1 day' : `${days} days`;
        }
    },

    /**
     * Calculate vesting progress percentage
     * @param {number} unlocked - Amount unlocked (in wei)
     * @param {number} total - Total vesting amount (in wei)
     * @returns {number} Percentage (0-100)
     */
    calculateProgress(unlocked, total) {
        if (!total || total === 0) return 0;
        const progress = (parseFloat(unlocked) / parseFloat(total)) * 100;
        return Math.min(Math.max(progress, 0), 100);
    },

    /**
     * Format next unlock timestamp
     * @param {string} vestingType - 'marketing' | 'team' | 'airdrops'
     * @param {number} startTime - Unix timestamp of vesting start
     * @param {number} claimed - Amount already claimed (in wei)
     * @param {number} total - Total vesting amount (in wei)
     * @returns {string} Human-readable next unlock time or "Fully unlocked"
     */
    formatNextUnlock(vestingType, startTime, claimed, total) {
        const now = Math.floor(Date.now() / 1000);
        const schedule = this.VESTING_SCHEDULES[vestingType];
        
        if (!schedule) return 'Unknown';

        const cliffEnd = startTime + schedule.cliff;
        const vestingEnd = startTime + schedule.duration;

        if (parseFloat(claimed) >= parseFloat(total)) {
            return 'Fully claimed';
        }

        if (now < cliffEnd) {
            return this.formatTimestamp(cliffEnd) + ' (cliff ends)';
        }

        if (now >= vestingEnd) {
            return 'All tokens unlocked';
        }

        return 'Unlocking now (linear)';
    },

    /**
     * Format timestamp to readable date
     * @param {number} timestamp - Unix timestamp
     * @returns {string} Formatted date
     */
    formatTimestamp(timestamp) {
        const date = new Date(timestamp * 1000);
        const now = new Date();
        const diffMs = date - now;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        if (diffDays < 0) {
            return date.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric', 
                year: 'numeric' 
            });
        } else if (diffDays === 0) {
            return 'Today';
        } else if (diffDays === 1) {
            return 'Tomorrow';
        } else if (diffDays < 7) {
            return `In ${diffDays} days`;
        } else if (diffDays < 30) {
            const weeks = Math.floor(diffDays / 7);
            return `In ${weeks} ${weeks === 1 ? 'week' : 'weeks'}`;
        } else if (diffDays < 365) {
            const months = Math.floor(diffDays / 30);
            return `In ${months} ${months === 1 ? 'month' : 'months'}`;
        } else {
            return date.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric', 
                year: 'numeric' 
            });
        }
    },

    /**
     * Format token amount from wei to human-readable
     * @param {string|number} wei - Amount in wei (18 decimals)
     * @param {number} decimals - Token decimals (default 18)
     * @param {number} displayDecimals - Number of decimals to display (default 2)
     * @returns {string} Formatted token amount
     */
    formatTokenAmount(wei, decimals = 18, displayDecimals = 2) {
        if (!wei) return '0';
        
        const tokens = parseFloat(wei) / Math.pow(10, decimals);
        
        if (tokens >= 1e9) {
            return (tokens / 1e9).toFixed(displayDecimals) + 'B';
        } else if (tokens >= 1e6) {
            return (tokens / 1e6).toFixed(displayDecimals) + 'M';
        } else if (tokens >= 1e3) {
            return (tokens / 1e3).toFixed(displayDecimals) + 'K';
        } else {
            return tokens.toFixed(displayDecimals);
        }
    },

    /**
     * Calculate available amount to withdraw
     * @param {number} unlocked - Total unlocked amount (in wei)
     * @param {number} claimed - Already claimed amount (in wei)
     * @returns {string} Available amount (in wei)
     */
    calculateAvailable(unlocked, claimed) {
        const available = parseFloat(unlocked) - parseFloat(claimed);
        return Math.max(available, 0).toString();
    },

    /**
     * Get vesting schedule info
     * @param {string} vestingType - 'marketing' | 'team' | 'airdrops'
     * @returns {object} Schedule configuration
     */
    getScheduleInfo(vestingType) {
        return this.VESTING_SCHEDULES[vestingType] || null;
    },

    /**
     * Calculate unlocked amount at current time
     * @param {number} total - Total vesting amount
     * @param {number} startTime - Vesting start timestamp
     * @param {number} cliff - Cliff duration in seconds
     * @param {number} duration - Total vesting duration in seconds
     * @returns {number} Unlocked amount
     */
    calculateUnlocked(total, startTime, cliff, duration) {
        const now = Math.floor(Date.now() / 1000);
        const cliffEnd = startTime + cliff;
        const vestingEnd = startTime + duration;

        if (now < cliffEnd) {
            return 0;
        }

        if (now >= vestingEnd) {
            return total;
        }

        const timeSinceCliff = now - cliffEnd;
        const vestingDuration = vestingEnd - cliffEnd;
        const unlocked = (total * timeSinceCliff) / vestingDuration;

        return Math.floor(unlocked);
    },

    /**
     * Validate vesting allocation percentages
     * @param {number} marketing - Marketing allocation %
     * @param {number} team - Team allocation %
     * @param {number} airdrops - Airdrops allocation %
     * @returns {boolean} True if valid (sums to 100)
     */
    validateAllocations(marketing, team, airdrops) {
        const sum = parseFloat(marketing) + parseFloat(team) + parseFloat(airdrops);
        return Math.abs(sum - 100) < 0.01;
    }
};

// Make available globally
window.VestingUtils = VestingUtils;
