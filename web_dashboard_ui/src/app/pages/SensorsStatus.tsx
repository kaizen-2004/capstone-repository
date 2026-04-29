import { useEffect, useState } from 'react';
import { Camera, Flame, Gauge, Server, WifiOff, CheckCircle2, AlertTriangle } from 'lucide-react';
import { fetchLiveNodes } from '../data/liveApi';
import type { SensorStatus, ServiceStatus } from '../data/types';
import { StatusBadge } from '../components/StatusBadge';

export function SensorsStatus() {
  const [sensorStatuses, setSensorStatuses] = useState<SensorStatus[]>([]);
  const [serviceStatuses, setServiceStatuses] = useState<ServiceStatus[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const live = await fetchLiveNodes();
        if (cancelled) {
          return;
        }
        setSensorStatuses(live.sensorStatuses);
        setServiceStatuses(live.serviceStatuses);
        setLoadError('');
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unable to load live node data.';
        if (!cancelled) {
          setLoadError(message);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void load();
    const timer = window.setInterval(() => {
      void load();
    }, 10000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const getIcon = (type: SensorStatus['type']) => {
    switch (type) {
      case 'camera':
        return <Camera className="w-6 h-6" />;
      case 'smoke':
        return <Flame className="w-6 h-6" />;
      case 'force':
        return <Gauge className="w-6 h-6" />;
    }
  };

  const getStatusColor = (status: SensorStatus['status']) => {
    switch (status) {
      case 'online':
        return 'bg-green-50 text-green-600';
      case 'offline':
        return 'bg-gray-50 text-gray-600';
      case 'warning':
        return 'bg-orange-50 text-orange-600';
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  const onlineNodes = sensorStatuses.filter((s) => s.status === 'online').length;
  const warningNodes = sensorStatuses.filter((s) => s.status === 'warning').length;
  const offlineNodes = sensorStatuses.filter((s) => s.status === 'offline').length;

  const onlineServices = serviceStatuses.filter((s) => s.status === 'online').length;
  const roomEntries = Object.entries(
    sensorStatuses.reduce<Record<string, SensorStatus[]>>((acc, sensor) => {
      const location = String(sensor.location || 'Unassigned Area').trim() || 'Unassigned Area';
      if (!acc[location]) {
        acc[location] = [];
      }
      acc[location].push(sensor);
      return acc;
    }, {}),
  ).sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="p-3 sm:p-4 md:p-8 space-y-5 md:space-y-6 overflow-x-hidden">
      <div>
        <h2 className="text-xl md:text-2xl font-semibold text-gray-900">Sensors & Nodes</h2>
        <p className="text-sm md:text-base text-gray-600 mt-1">
          Operational status for all deployed nodes and runtime services.
        </p>
      </div>

      {loadError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Live node data unavailable: {loadError}
        </div>
      )}
      {isLoading && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
          Loading live node health...
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <p className="text-sm text-gray-600">Online Nodes</p>
          <p className="text-3xl font-semibold text-green-600 mt-1">{onlineNodes}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <p className="text-sm text-gray-600">Warning Nodes</p>
          <p className="text-3xl font-semibold text-orange-600 mt-1">{warningNodes}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <p className="text-sm text-gray-600">Offline Nodes</p>
          <p className="text-3xl font-semibold text-gray-600 mt-1">{offlineNodes}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <p className="text-sm text-gray-600">Online Services</p>
          <p className="text-3xl font-semibold text-blue-600 mt-1">{onlineServices}</p>
        </div>
      </div>

      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Room Map</h3>
          <p className="text-sm text-gray-600">Live node health grouped by reported deployment area.</p>
        </div>
        <div className="space-y-4">
          {roomEntries.map(([room, sensors]) => {
            const roomWarnings = sensors.filter((sensor) => sensor.status === 'warning').length;
            const roomOffline = sensors.filter((sensor) => sensor.status === 'offline').length;
            const roomSeverity = roomOffline > 0 ? 'offline' : roomWarnings > 0 ? 'warning' : 'online';

            return (
              <section key={room} className="rounded-xl border border-gray-200 bg-white p-4 sm:p-5">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
                  <div>
                    <h4 className="font-semibold text-gray-900">{room}</h4>
                    <p className="text-sm text-gray-600">{sensors.length} node{sensors.length === 1 ? '' : 's'} reporting</p>
                  </div>
                  <StatusBadge severity={roomSeverity} label={roomSeverity.toUpperCase()} size="sm" />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {sensors.map((sensor) => (
                    <div key={sensor.id} className="rounded-lg border border-gray-200 p-4 bg-gray-50/50">
                      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between mb-4 gap-3">
                        <div className="flex items-start gap-3 min-w-0">
                          <div className={`rounded-lg p-3 ${getStatusColor(sensor.status)}`}>{getIcon(sensor.type)}</div>
                          <div className="min-w-0">
                            <h3 className="font-semibold text-gray-900">{sensor.name}</h3>
                            <p className="text-xs font-mono text-gray-500 mt-1 break-all">{sensor.id}</p>
                          </div>
                        </div>
                        <div className="shrink-0">
                          <StatusBadge severity={sensor.status} label={sensor.status.toUpperCase()} size="sm" />
                        </div>
                      </div>

                      <div className="space-y-2 pt-4 border-t border-gray-200 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="text-gray-600">Last Update</span>
                          <span className="font-medium text-gray-900">{formatTime(sensor.lastUpdate)}</span>
                        </div>
                        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-1 sm:gap-4">
                          <span className="text-gray-600">Node Note</span>
                          <span className="font-medium text-gray-900 sm:text-right break-words">{sensor.note}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            );
          })}
          {sensorStatuses.length === 0 && !isLoading && (
            <div className="rounded-lg border border-gray-200 bg-white p-5 text-sm text-gray-600">
              No live sensor nodes reported by the backend.
            </div>
          )}
        </div>
      </div>

      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-gray-900">Runtime Services</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {serviceStatuses.map((service) => (
            <div key={service.id} className="bg-white rounded-lg border border-gray-200 p-5">
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between mb-4 gap-3">
                <div className="flex items-start gap-3 min-w-0">
                  <div className="rounded-lg p-3 bg-blue-50 text-blue-600">
                    <Server className="w-6 h-6" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="font-semibold text-gray-900">{service.name}</h3>
                    <p className="text-xs font-mono text-gray-500 mt-1 break-all">{service.endpoint}</p>
                  </div>
                </div>
                <div className="shrink-0">
                  <StatusBadge severity={service.status} label={service.status.toUpperCase()} size="sm" />
                </div>
              </div>

              <div className="space-y-2 pt-4 border-t border-gray-200 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">Last Update</span>
                  <span className="font-medium text-gray-900">{formatTime(service.lastUpdate)}</span>
                </div>
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-1 sm:gap-4">
                  <span className="text-gray-600">Detail</span>
                  <span className="font-medium text-gray-900 sm:text-right break-words">{service.detail}</span>
                </div>
              </div>
            </div>
          ))}
          {serviceStatuses.length === 0 && !isLoading && (
            <div className="rounded-lg border border-gray-200 bg-white p-5 text-sm text-gray-600">
              No runtime service health reported by the backend.
            </div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <h3 className="font-semibold text-gray-900 mb-4">Node Health Summary</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
          <div className="flex items-center gap-2 text-green-700">
            <CheckCircle2 className="w-4 h-4" />
            <span>Stable nodes: {onlineNodes}</span>
          </div>
          <div className="flex items-center gap-2 text-orange-700">
            <AlertTriangle className="w-4 h-4" />
            <span>Needs attention: {warningNodes}</span>
          </div>
          <div className="flex items-center gap-2 text-gray-700">
            <WifiOff className="w-4 h-4" />
            <span>Offline nodes: {offlineNodes}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
