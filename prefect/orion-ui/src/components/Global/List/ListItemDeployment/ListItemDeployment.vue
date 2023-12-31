<template>
  <ListItem class="list-item--deployment" icon="pi-map-pin-line">
    <div class="list-item__title">
      <h2>
        {{ item.name }}
      </h2>

      <div
        class="
          tag-container
          font-weight-semibold
          nowrap
          caption
          d-flex
          align-bottom
        "
      >
        <span
          v-if="schedule"
          class="mr-1 caption text-truncate d-flex align-center"
        >
          <i class="pi pi-calendar-line pi-sm text--grey-20" />
          <span
            class="text--grey-80 ml--half font--primary"
            style="min-width: 0px"
          >
            {{ schedule !== '--' ? 'Every' : '' }} {{ schedule }}
          </span>
        </span>

        <span class="mr-1 caption text-truncate d-flex align-center">
          <i class="pi pi-global-line pi-sm text--grey-20" />
          <span
            class="text--grey-80 ml--half font--primary"
            style="min-width: 0px"
          >
            {{ location }}
          </span>
        </span>

        <span class="mr-1 text-truncate caption">
          <Tags :tags="tags" />
        </span>
      </div>
    </div>

    <div v-if="media.sm" class="ml-auto d-flex align-middle nowrap">
      <Toggle v-if="false" v-model="scheduleActive" />

      <Button
        outlined
        height="36px"
        width="160px"
        class="mr-1 text--grey-80"
        @click="parametersDrawerActive = true"
      >
        View Parameters
      </Button>
      <Button
        outlined
        miter
        height="36px"
        width="105px"
        class="text--grey-80"
        :disabled="creatingRun"
        @click="createRun"
      >
        Quick Run
      </Button>
    </div>
  </ListItem>

  <Drawer v-model="parametersDrawerActive" show-overlay>
    <template #title>{{ item.name }}</template>
    <h3 class="font-weight-bold">Parameters</h3>
    <div>These are the inputs that are passed to runs of this Deployment.</div>

    <hr class="mt-2 parameters-hr align-self-stretch" />

    <Input v-model="search" placeholder="Search...">
      <template #prepend>
        <i class="pi pi-search-line"></i>
      </template>
    </Input>

    <div class="mt-2 font--secondary">
      {{ filteredParameters.length }} result{{
        filteredParameters.length !== 1 ? 's' : ''
      }}
    </div>

    <hr class="mt-2 parameters-hr" />

    <div class="parameters-container pr-2 align-self-stretch">
      <div v-for="(parameter, i) in filteredParameters" :key="i">
        <div class="d-flex align-center justify-space-between">
          <div class="caption font-weight-bold font--secondary">
            {{ parameter.name }}
          </div>
          <span
            class="
              parameter-type
              font--secondary
              caption-small
              px-1
              text--white
            "
          >
            {{ parameter.type }}
          </span>
        </div>

        <p class="font--secondary caption">
          {{ parameter.value }}
        </p>

        <hr
          v-if="i !== filteredParameters.length - 1"
          class="mb-2 parameters-hr"
        />
      </div>
    </div>
  </Drawer>
</template>

<script lang="ts">
import { Options, Vue, prop } from 'vue-class-component'
import { secondsToString } from '@/util/util'
import { Deployment } from '@/typings/objects'
import { Api, Endpoints } from '@/plugins/api'
import media from '@/utilities/media'

class Props {
  item = prop<Deployment>({ required: true })
}

@Options({
  watch: {
    parametersDrawerActive() {
      this.search = ''
    },
    async scheduleActive(val) {
      const endpoint = val ? 'set_schedule_active' : 'set_schedule_inactive'

      Api.query({
        endpoint: Endpoints[endpoint],
        body: { id: this.item.id }
      })
    }
  }
})
export default class ListItemDeployment extends Vue.with(Props) {
  parametersDrawerActive: boolean = false
  search: string = ''
  scheduleActive: boolean = this.item.is_schedule_active
  creatingRun: boolean = false
  media = media

  async createRun(): Promise<void> {
    this.creatingRun = true
    const res = await Api.query({
      endpoint: Endpoints.create_flow_run_from_deployment,
      body: {
        id: this.item.id,
        state: {
          type: 'SCHEDULED',
          message: 'Quick run through the Orion UI.'
        }
      }
    })
    this.$toast({
      type: res.error ? 'error' : 'success',
      message: res.error
        ? `Error: ${res.error}`
        : res.response.value?.name
        ? `Run created: ${res.response.value?.name}`
        : 'Run created',
      timeout: 10000
    })
    this.creatingRun = false
  }

  get location(): string {
    return this.item.flow_data.blob || '--'
  }

  get parameters(): { [key: string]: any }[] {
    return Object.entries(this.item.parameters).reduce(
      (arr: { [key: string]: any }[], [key, value]) => [
        ...arr,
        { name: key, value: value, type: typeof value }
      ],
      []
    )
  }

  get schedule(): string {
    if (!this.item.schedule) return '--'
    if ('interval' in this.item.schedule)
      return secondsToString(this.item.schedule.interval, false)

    // TODO: add parsing for cron and RR schedules
    return '--'
  }

  get tags(): string[] {
    return this.item.tags
  }

  get filteredParameters(): { [key: string]: any }[] {
    return this.parameters.filter(
      (p) => p.name.includes(this.search) || p.type.includes(this.search)
    )
  }
}
</script>

<style lang="scss" scoped>
.tag-container {
  margin-top: 6px;

  > .tag-wrapper {
    margin-top: -4px;
  }
}

.parameters-hr {
  border: 0;
  border-bottom: 1px solid;
  color: $grey-10 !important;
  width: 100%;
}

.parameter-type {
  background-color: $grey-40;
  border-radius: 4px;
}

.parameters-container {
  overflow: auto;
}
</style>
