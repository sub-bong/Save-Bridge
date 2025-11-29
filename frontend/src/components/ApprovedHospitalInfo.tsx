import React from "react";
import type { Hospital } from "../types";

interface ApprovedHospitalInfoProps {
  approvedHospital: Hospital;
}

export const ApprovedHospitalInfo: React.FC<ApprovedHospitalInfoProps> = ({ approvedHospital }) => {
  return (
    <section className="bg-white rounded-lg shadow-md p-6 border-2 border-green-500">
      <h2 className="text-lg font-bold mb-3 text-green-800 border-b-2 border-green-500 pb-2">승인된 병원</h2>
      <div className="p-4 bg-green-50 rounded-lg border-2 border-green-300">
        <p className="text-base font-bold text-gray-900 mb-2">{approvedHospital.dutyName}</p>
        <p className="text-sm text-gray-700 mb-1">{approvedHospital.dutyAddr}</p>
        {approvedHospital.dutytel3 && (
          <p className="text-sm text-gray-700 font-semibold">전화: {approvedHospital.dutytel3}</p>
        )}
      </div>
    </section>
  );
};

