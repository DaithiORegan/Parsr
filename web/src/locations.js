export const COUNTIES=['Carlow','Cavan','Clare','Cork','Donegal','Dublin','Galway','Kerry','Kildare','Kilkenny','Laois','Leitrim','Limerick','Longford','Louth','Mayo','Meath','Monaghan','Offaly','Roscommon','Sligo','Tipperary','Waterford','Westmeath','Wexford','Wicklow'];
const towns={Kerry:['tralee','killarney','kenmare','listowel','dingle','killorglin','castleisland','cahersiveen','ballybunion'],Cork:['mallow','midleton','cobh','fermoy','clonakilty','bantry','skibbereen','little island','ballincollig','carrigaline','bandon','kinsale','youghal','macroom'],Mayo:['castlebar','ballina','westport'],Donegal:['letterkenny','bundoran'],Louth:['dundalk','drogheda'],Westmeath:['athlone','mullingar']};
export function locationMatches(job, location){
 if(!location||location==='All locations')return true;
 const text=String(job.location||'').toLowerCase();
 if(location==='Cork & Kerry')return locationMatches(job,'Cork')||locationMatches(job,'Kerry');
 return [location,...(towns[location]||[])].some(term=>text.includes(term.toLowerCase()));
}
