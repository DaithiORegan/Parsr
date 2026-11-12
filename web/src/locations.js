import towns from "../../config/irish_locations.json";
export const COUNTIES=['Carlow','Cavan','Clare','Cork','Donegal','Dublin','Galway','Kerry','Kildare','Kilkenny','Laois','Leitrim','Limerick','Longford','Louth','Mayo','Meath','Monaghan','Offaly','Roscommon','Sligo','Tipperary','Waterford','Westmeath','Wexford','Wicklow'];
export function locationMatches(job, location){
 if(!location||location==='All locations')return true;
 const text=String(job.location||'').toLowerCase();
 if(location==='Cork & Kerry')return locationMatches(job,'Cork')||locationMatches(job,'Kerry');
 return [location,...(towns[location]||[])].some(term=>text.includes(term.toLowerCase()));
}
