import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../api/torrents.js', () => {
  return {
    fetchActiveDownloads: vi.fn().mockResolvedValue({}),
    getDownloadStatusByKpId: vi.fn(),
    getTorrentStatusForLibrary: vi.fn(),
    getTorrentStatusForLottery: vi.fn()
  };
});

import { StatusWidgetManager } from '../statusWidget.js';
import { getDownloadStatusByKpId } from '../../api/torrents.js';

function createWidgetMarkup() {
  document.body.innerHTML = `
    <div id="widget">
      <div class="widget-header"></div>
      <button id="widget-toggle-btn"></button>
      <div class="widget-empty"></div>
      <div id="widget-downloads"></div>
    </div>
  `;
  return document.getElementById('widget');
}

describe('StatusWidgetManager.poll', () => {
  let widgetElement;
  let manager;

  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    sessionStorage.clear();
    widgetElement = createWidgetMarkup();
    manager = new StatusWidgetManager(widgetElement, 'testStorage');
    manager.activeDownloads.clear();
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    document.body.innerHTML = '';
    localStorage.clear();
    sessionStorage.clear();
  });

  it('updates the progress information when polling succeeds', async () => {
    const entry = {
      key: 'kp-123',
      id: 123,
      type: 'kinopoisk',
      movieName: 'Test Movie'
    };

    manager.getOrCreateDownloadElement(entry.key, `Загрузка: ${entry.movieName}`);

    getDownloadStatusByKpId.mockResolvedValueOnce({
      status: 'downloading',
      name: 'Test Movie',
      progress: 42.5,
      speed: '1.50',
      eta: '00:10',
      seeds: 5,
      peers: 10
    });

    await manager.poll(entry);

    const downloadElement = widgetElement.querySelector(`[data-download-key="${entry.key}"]`);
    expect(downloadElement).not.toBeNull();

    const progressBar = downloadElement.querySelector('.progress-bar');
    const progressText = downloadElement.querySelector('.progress-text');
    const speedText = downloadElement.querySelector('.speed-text');
    const etaText = downloadElement.querySelector('.eta-text');
    const peersText = downloadElement.querySelector('.peers-text');

    expect(progressBar.style.width).toBe('42.5%');
    expect(progressText.textContent).toBe('43%');
    expect(speedText.textContent).toBe('1.50 МБ/с');
    expect(etaText.textContent).toBe('00:10');
    expect(peersText.textContent).toBe('Сиды: 5 / Пиры: 10');
  });

  it('removes finished downloads after completion', async () => {
    const entry = {
      key: 'kp-456',
      id: 456,
      type: 'kinopoisk',
      movieName: 'Completed Movie'
    };

    manager.activeDownloads.set(entry.key, entry);
    manager.getOrCreateDownloadElement(entry.key, `Загрузка: ${entry.movieName}`);

    getDownloadStatusByKpId.mockResolvedValueOnce({
      status: 'Seeding',
      name: 'Completed Movie',
      progress: 100,
      speed: '0.00',
      eta: '--:--',
      seeds: 12,
      peers: 0
    });

    await manager.poll(entry);

    const speedText = widgetElement.querySelector(`[data-download-key="${entry.key}"] .speed-text`);
    expect(speedText.textContent).toBe('Готово');

    vi.advanceTimersByTime(5000);

    expect(manager.activeDownloads.has(entry.key)).toBe(false);
    expect(widgetElement.querySelector(`[data-download-key="${entry.key}"]`)).toBeNull();
  });
});
