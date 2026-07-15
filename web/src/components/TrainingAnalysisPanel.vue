<template>
  <div class="row mt-3">
    <div class="col-sm-6 d-flex align-items-stretch">
      <div class="card w-100 d-flex flex-column" style="min-height: 280px;">
        <div class="card-header d-flex align-items-center">
          <span class="card-title mb-0">Last 5 Training Decisions</span>
        </div>
        <div class="card-body d-flex flex-column justify-content-center p-3">
          <div v-if="!recentTrainings || recentTrainings.length === 0" class="text-center text-muted py-4">
            No training decisions found.
          </div>
          <div v-else class="table-responsive w-100">
            <table class="table table-sm table-dark mb-0" style="background: transparent; color: inherit; font-size: 13px;">
              <thead>
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                  <th style="border-top: none;">Turn</th>
                  <th style="border-top: none;">Decision</th>
                  <th style="border-top: none;" class="text-right">Score</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in recentTrainings" :key="item.date" style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                  <td class="align-middle">Day {{ item.date }}</td>
                  <td class="align-middle">
                    <span class="badge" :class="getBadgeClass(item.action)">
                      {{ formatActionName(item.action) }}
                    </span>
                  </td>
                  <td class="align-middle text-right font-weight-bold" style="color: var(--accent-2);">
                    {{ item.score ? item.score.toFixed(2) : '—' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
    <div class="col-sm-6 d-flex align-items-stretch">
      <div class="card w-100 d-flex flex-column" style="min-height: 280px;">
        <div class="card-header">
          <span class="card-title mb-0">Total Stats Gained</span>
        </div>
        <div class="card-body p-2 d-flex flex-column justify-content-center" style="position: relative;">
          <div v-if="completedTrainings.length === 0" class="text-center text-muted py-5" style="font-size: 13px; width: 100%;">
            No completed training gains to plot.
          </div>
          <div v-else class="chart-container" style="position: relative; width: 100%;">
            <svg viewBox="0 0 320 180" class="w-100" style="display: block;">
              <defs>
                <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.3" />
                  <stop offset="100%" stop-color="var(--accent)" stop-opacity="0" />
                </linearGradient>
              </defs>
              
              <line x1="40" y1="30" x2="280" y2="30" stroke="rgba(255,255,255,0.05)" stroke-dasharray="2,2" />
              <line x1="40" y1="80" x2="280" y2="80" stroke="rgba(255,255,255,0.05)" stroke-dasharray="2,2" />
              <line x1="40" y1="130" x2="280" y2="130" stroke="rgba(255,255,255,0.05)" stroke-dasharray="2,2" />
              
              <path v-if="chartPoints.length > 0" :d="areaPathD" fill="url(#chartGrad)" />
              <path v-if="chartPoints.length > 0" :d="linePathD" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
              
              <g v-for="(p, index) in chartPoints" :key="index">
                <text :x="p.x" :y="p.y - 8" text-anchor="middle" fill="#fff" font-weight="bold" font-size="9">+{{ p.item.gain }}</text>
                <text :x="p.x" :y="156" text-anchor="middle" fill="var(--muted)" font-size="8">D{{ p.item.date }}</text>
                <text :x="p.x" :y="168" text-anchor="middle" fill="var(--muted-2)" font-size="8">{{ formatShortActionName(p.item.action) }}</text>
                
                <circle 
                  :cx="p.x" 
                  :cy="p.y" 
                  r="5" 
                  fill="var(--accent-2)" 
                  stroke="var(--surface)" 
                  stroke-width="1.5" 
                  style="cursor: pointer;"
                  @mouseenter="hoveredPoint = p" 
                  @mouseleave="hoveredPoint = null"
                />
                <circle 
                  :cx="p.x" 
                  :cy="p.y" 
                  r="12" 
                  fill="transparent" 
                  style="cursor: pointer;"
                  @mouseenter="hoveredPoint = p" 
                  @mouseleave="hoveredPoint = null"
                />
              </g>
            </svg>
            
            <div v-if="hoveredPoint" class="chart-tooltip" :style="{ left: tooltipLeft, top: tooltipTop }">
              <div class="tooltip-title">{{ formatActionName(hoveredPoint.item.action) }} (Day {{ hoveredPoint.item.date }})</div>
              <div class="tooltip-total">Total Gain: +{{ hoveredPoint.item.gain }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "TrainingAnalysisPanel",
  props: {
    recentTrainings: {
      type: Array,
      default: () => []
    }
  },
  data() {
    return {
      hoveredPoint: null
    };
  },
  computed: {
    completedTrainings() {
      if (!this.recentTrainings) return [];
      return this.recentTrainings.filter(t => t.gain !== null && t.gain !== undefined);
    },
    chartPoints() {
      if (!this.completedTrainings || this.completedTrainings.length === 0) return [];
      const gains = this.completedTrainings.map(t => t.gain);
      const minGain = Math.min(...gains);
      const maxGain = Math.max(...gains);
      const range = maxGain - minGain;
      
      const width = 320;
      const height = 180;
      const padX = 40;
      const padY = 40;
      
      return this.completedTrainings.map((t, i) => {
        let x = padX;
        if (this.completedTrainings.length > 1) {
          x = padX + (i / (this.completedTrainings.length - 1)) * (width - 2 * padX);
        } else {
          x = width / 2;
        }
        
        let y = height - padY;
        if (range > 0) {
          y = height - padY - ((t.gain - minGain) / range) * (height - 2 * padY);
        } else {
          y = (height - padY) / 2 + padY / 2;
        }
        return { x, y, item: t };
      });
    },
    linePathD() {
      if (this.chartPoints.length === 0) return '';
      return this.chartPoints.map((p, i) => (i === 0 ? 'M' : 'L') + ' ' + p.x + ' ' + p.y).join(' ');
    },
    areaPathD() {
      if (this.chartPoints.length === 0) return '';
      const lineD = this.linePathD;
      const firstX = this.chartPoints[0].x;
      const lastX = this.chartPoints[this.chartPoints.length - 1].x;
      return `${lineD} L ${lastX} 140 L ${firstX} 140 Z`;
    },
    tooltipLeft() {
      if (!this.hoveredPoint) return '0px';
      return `${(this.hoveredPoint.x / 320) * 100}%`;
    },
    tooltipTop() {
      if (!this.hoveredPoint) return '0px';
      return `${(this.hoveredPoint.y / 180) * 100}%`;
    }
  },
  methods: {
    formatActionName(action) {
      const map = {
        'TRAINING_TYPE_SPEED': 'Speed',
        'TRAINING_TYPE_STAMINA': 'Stamina',
        'TRAINING_TYPE_POWER': 'Power',
        'TRAINING_TYPE_WILL': 'Guts',
        'TRAINING_TYPE_INTELLIGENCE': 'Wit'
      };
      return map[action] || action;
    },
    formatShortActionName(action) {
      const map = {
        'TRAINING_TYPE_SPEED': 'Spd',
        'TRAINING_TYPE_STAMINA': 'Sta',
        'TRAINING_TYPE_POWER': 'Pow',
        'TRAINING_TYPE_WILL': 'Gut',
        'TRAINING_TYPE_INTELLIGENCE': 'Wit'
      };
      return map[action] || action;
    },
    getBadgeClass(action) {
      const map = {
        'TRAINING_TYPE_SPEED': 'badge-primary',
        'TRAINING_TYPE_STAMINA': 'badge-info',
        'TRAINING_TYPE_POWER': 'badge-warning',
        'TRAINING_TYPE_WILL': 'badge-danger',
        'TRAINING_TYPE_INTELLIGENCE': 'badge-success'
      };
      return map[action] || 'badge-secondary';
    }
  }
};
</script>

<style scoped>
.chart-container {
  position: relative;
  width: 100%;
}
.chart-tooltip {
  position: absolute;
  transform: translate(-50%, -100%);
  background: rgba(20, 15, 24, 0.95);
  border: 1px solid var(--accent);
  border-radius: 6px;
  padding: 8px 12px;
  pointer-events: none;
  z-index: 10;
  box-shadow: 0 4px 12px rgba(0,0,0,0.5);
  font-size: 11px;
  color: #fff;
  white-space: nowrap;
}
.tooltip-title {
  font-weight: 700;
  color: var(--accent-2);
  margin-bottom: 2px;
}
.tooltip-total {
  font-weight: 600;
  margin-bottom: 4px;
}
</style>
