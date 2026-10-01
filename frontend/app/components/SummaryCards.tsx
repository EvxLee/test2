const SummaryCards = () => {
  const totals = {
    allYears: 0,
    yes: 0,
    yesForLater: 0,
  };

  return (
    <div className="grid grid-cols-3 gap-6 mt-6">
      <div className="bg-white text-center p-5 rounded-lg shadow">
        <p className="text-gray-500 text-sm">Total Startups (All Years)</p>
        <h2 className="text-3xl font-bold text-[#8B1E2F]">{totals.allYears}</h2>
      </div>

      <div className="bg-white text-center p-5 rounded-lg shadow">
        <p className="text-gray-500 text-sm">Total "Yes" Classifications</p>
        <h2 className="text-3xl font-bold text-green-600">{totals.yes}</h2>
      </div>

      <div className="bg-white text-center p-5 rounded-lg shadow">
        <p className="text-gray-500 text-sm">Total "Yes for Later"</p>
        <h2 className="text-3xl font-bold text-yellow-600">
          {totals.yesForLater}
        </h2>
      </div>
    </div>
  );
};

export default SummaryCards;

