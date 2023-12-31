<template>
  <div
    class="
      search-input
      px-2
      flex-grow-1 flex-shrink-0
      d-flex
      align-center
      font--primary
      justify-start
    "
    @click.self="focusSearchInput"
  >
    <i class="pi pi-search-line mr-1 flex-shrink-1" />
    <input
      v-model="search"
      ref="searchInput"
      class="flex-shrink-1"
      placeholder="Search..."
      @focus="emitFocused"
      @input="emitInput"
      @keyup.enter="emitEnter"
    />
    <div
      v-if="media.xs"
      class="
        ml-auto
        d-flex
        align-center
        justify-end
        flex-shrink-0 flex-grow-1
        slot-content
      "
      @click.self="focusSearchInput"
    >
      <slot />
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import media from '@/utilities/media'

const emit = defineEmits(['input', 'keyup.enter', 'focused'])
const searchInput = ref()
const search = ref('')

const emitInput = () => {
  emit('input', search.value)
}

const emitEnter = () => {
  emit('keyup.enter', search.value)
}

const emitFocused = () => {
  emit('focused')
}

const focusSearchInput = () => {
  searchInput.value.focus()
}

const handleKeyboardEvent = (e: KeyboardEvent) => {
  if (!e?.target) return
  const target = e.target as HTMLElement
  switch (target.tagName) {
    case 'INPUT':
    case 'SELECT':
    case 'TEXTAREA':
      return
  }

  if (e.key == 't' && e.target) {
    focusSearchInput()
  }
}

onMounted(() => {
  window.addEventListener('keyup', handleKeyboardEvent)
})

onBeforeUnmount(() => {
  window.removeEventListener('keyup', handleKeyboardEvent)
})
</script>

<style lang="scss" scoped>
.search-input {
  position: relative;

  input {
    border: none;
    outline: none;
    height: 100%;
  }

  .slot-content {
    max-width: 90%;
    z-index: 1;
  }
}
</style>
