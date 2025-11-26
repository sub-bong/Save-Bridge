import React from "react";
import type { Coords, Region } from "../types";

interface LocationInputProps {
  address: string;
  setAddress: (address: string) => void;
  coords: Coords;
  region: Region | null;
  loadingGps: boolean;
  onSearchAddress: () => void;
  onGpsClick: () => void;
}

export const LocationInput: React.FC<LocationInputProps> = ({
  address,
  setAddress,
  coords,
  region,
  loadingGps,
  onSearchAddress,
  onGpsClick,
}) => {
  return (
    <section className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
      <h2 className="text-lg font-bold mb-4 text-gray-900 border-b-2 border-gray-300 pb-2">
        환자 위치 정보
      </h2>
      <div className="flex flex-col md:flex-row gap-3 items-end">
        <div className="flex-1 flex flex-col gap-2">
          <label className="text-sm font-semibold text-gray-700">주소 입력</label>
          <input
            className="w-full rounded-lg border-2 border-gray-300 px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="예: 서울특별시 종로구 종로1길 50"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === "Enter") {
                onSearchAddress();
              }
            }}
          />
        </div>
        <button
          className="md:w-24 h-12 rounded-lg bg-blue-600 text-white text-base font-semibold flex items-center justify-center hover:bg-blue-700 active:bg-blue-800 transition shadow-md"
          onClick={onSearchAddress}
        >
          검색
        </button>
        <button
          className="md:w-32 h-12 rounded-lg bg-gray-800 text-white text-base font-semibold flex items-center justify-center hover:bg-gray-900 active:bg-gray-950 transition shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={onGpsClick}
          disabled={loadingGps}
        >
          {loadingGps ? <span className="text-sm">로딩 중...</span> : <span>GPS 위치</span>}
        </button>
      </div>
      <div className="mt-4 text-sm text-gray-600 flex flex-wrap gap-4">
        <span>
          현재 좌표:{" "}
          <span className="font-mono font-semibold">
            {coords.lat && coords.lon
              ? `${coords.lat.toFixed(6)}, ${coords.lon.toFixed(6)}`
              : "—, —"}
          </span>
        </span>
        {region && (
          <span>
            행정구역: <span className="font-semibold">{region.sido} {region.sigungu}</span>
          </span>
        )}
      </div>
    </section>
  );
};

